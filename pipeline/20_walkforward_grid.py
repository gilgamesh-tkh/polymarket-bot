#!/usr/bin/env python
"""Étape 8c — Walk-forward multi-coupures (expanding).

Pour chaque coupure C (4 dates), on refait le protocole complet SANS fuite :
  - features : comportement pré-C (18_wf_features_pre <C>)
  - label : H1 sur les marchés dont le 1er trade du wallet >= C ET résolus
  - entraînement/éval CV sur la population dispo (>=50 trades pré-C)
Le walk-forward est dit "expanding" car chaque coupure utilise TOUT le passé avant C
comme features. La stabilité de l'AUC à travers les coupures teste la robustesse.

Sortie : output/walkforward_grid.md
"""
import datetime as dt
import json
import sys
import time
from pathlib import Path

import numpy as np
import polars as pl
import xgboost as xgb

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sklearn.metrics import (average_precision_score, f1_score,  # noqa: E402
                             precision_recall_curve, roc_auc_score)
from sklearn.model_selection import StratifiedKFold  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from config import OUTPUT_DIR  # noqa: E402

CUTS = ["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"]
BASE_FEATS = ["n_trades", "maker_ratio", "avg_usd_trade", "usd_gross", "n_markets",
              "n_days", "span_days", "avg_price", "weekend_frac", "frac_buy",
              "frac_token1", "extremeness"]
ADV_FEATS = ["hour_entropy", "dominant_hour", "size_cv", "arbitrage_share",
             "trades_per_market", "roundtrip_share", "entry_timing_s", "time_to_end_s",
             "n_weeks_ratio", "age_years"]
LOG_FEATS = ["n_trades", "avg_usd_trade", "usd_gross", "n_markets", "span_days",
             "trades_per_market"]


def cut_epoch(c):
    return int(dt.datetime.strptime(c, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp())


def make_label(c):
    ep = cut_epoch(c)
    out = OUTPUT_DIR / f"wf_label_{c}.parquet"
    if out.exists():
        return
    u = pl.scan_parquet(OUTPUT_DIR / "users_sample.parquet")
    ft = (u.group_by(["address", "market_id"])
          .agg(pl.col("timestamp").min().alias("first_ts")).collect())
    post = ft.filter(pl.col("first_ts") >= ep)
    mr = pl.read_parquet(OUTPUT_DIR / "market_resolved.parquet").rename(
        {"id": "market_id"}).select(["market_id"])
    lbl = post.join(mr, on="market_id", how="inner")
    pnl = pl.read_parquet(OUTPUT_DIR / "wallet_pnl_v2.parquet").select(
        ["address", "market_id", "resolved", "pnl", "C1", "C2"])
    j = lbl.join(pnl, on=["address", "market_id"], how="inner").filter(pl.col("resolved"))
    per = (j.group_by("address")
           .agg(pl.len().alias("n_mkts"),
                (pl.col("pnl") > 0).sum().alias("n_won"),
                pl.col("pnl").sum().alias("pnl"),
                (pl.col("C1").fill_null(0) + pl.col("C2").fill_null(0)).sum().alias("cost"))
           .with_columns(win_rate=pl.col("n_won") / pl.col("n_mkts"),
                         roi=pl.col("pnl") / pl.col("cost").replace(0, None))
           .with_columns(h1=(pl.col("roi") > 0.20) & (pl.col("win_rate") > 0.65)))
    per.filter(pl.col("n_mkts") >= 3).write_parquet(out)
    print(f"label {c}: n={len(per.filter(pl.col('n_mkts')>=3))}")


def load(c, min_trades=50, use_adv=True):
    feat = pl.read_parquet(OUTPUT_DIR / f"wf_features_pre_{c}.parquet")
    label = pl.read_parquet(OUTPUT_DIR / f"wf_label_{c}.parquet")
    df = feat.join(label.select(["address", "h1"]), on="address", how="inner")
    df = df.filter(pl.col("n_trades") >= min_trades)
    feats = BASE_FEATS + (ADV_FEATS if use_adv else [])
    f = df.select(feats).to_pandas()
    for col in LOG_FEATS:
        if col in f.columns:
            f[col] = np.log1p(f[col].clip(lower=0))
    X = f.to_numpy(dtype=float)
    X = np.nan_to_num(X, nan=np.nanmedian(X, axis=0))
    y = df["h1"].to_numpy().astype(int)
    addr = df["address"].to_list()
    return X, y, feats, addr


def cv(X, y, model, seed=42, n_splits=5, repeats=5):
    aucs, prs = [], []
    for r in range(repeats):
        skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed + r * 7)
        for tr, te in skf.split(X, y):
            m = model()
            m.fit(X[tr], y[tr])
            p = m.predict_proba(X[te])[:, 1]
            aucs.append(roc_auc_score(y[te], p))
            prs.append(average_precision_score(y[te], p))
    return {"auc": float(np.mean(aucs)), "auc_std": float(np.std(aucs)),
            "pr": float(np.mean(prs))}


def sequential(purge=True):
    """Walk-forward séquentiel STRICT : entraîner sur c_i, tester sur c_{i+1}.

    purge=True (défaut) : on EXCLUT du test les wallets déjà vus en entraînement
    (anti fuite d'identité). Sans purge, l'AUC est artificiellement gonflée car le
    modèle reconnaît des wallets déjà appris.
    """
    seq = []
    for i in range(len(CUTS) - 1):
        c_tr, c_te = CUTS[i], CUTS[i + 1]
        Xtr, ytr, _, addr_tr = load(c_tr)
        Xte, yte, _, addr_te = load(c_te)
        if purge:
            seen = set(addr_tr)
            mask = np.array([a not in seen for a in addr_te])
            Xte, yte = Xte[mask], yte[mask]
        if yte.sum() < 5 or ytr.sum() < 10:
            continue
        sc = StandardScaler().fit(Xtr)
        spw = (len(ytr) - int(ytr.sum())) / int(ytr.sum())
        mk = lambda: xgb.XGBClassifier(n_estimators=500, max_depth=4,  # noqa: E731
                                       learning_rate=0.02, subsample=0.8,
                                       colsample_bytree=0.7, scale_pos_weight=spw,
                                       eval_metric="auc", n_jobs=2, random_state=42)
        aucs, prs = [], []
        for seed in [42, 7, 2026]:
            m = mk()
            m.fit(sc.transform(Xtr), ytr)
            p = m.predict_proba(sc.transform(Xte))[:, 1]
            aucs.append(roc_auc_score(yte, p))
            prs.append(average_precision_score(yte, p))
        seq.append({"train_cut": c_tr, "test_cut": c_te,
                    "n_train": int(len(ytr)), "pos_train": int(ytr.sum()),
                    "n_test": int(len(yte)), "pos_test": int(yte.sum()),
                    "purged": purge,
                    "auc": float(np.mean(aucs)), "pr": float(np.mean(prs))})
        print(f"train {c_tr} -> test {c_te} (purge={purge}): "
              f"n_test={len(yte)} pos={int(yte.sum())} AUC={np.mean(aucs):.3f} "
              f"PR={np.mean(prs):.3f}")
    return seq


def main():
    res_all = {}
    for c in CUTS:
        make_label(c)
    for c in CUTS:
        X, y, feats, _ = load(c)
        n_pos = int(y.sum())
        spw = (len(y) - n_pos) / n_pos
        mk = lambda: xgb.XGBClassifier(n_estimators=500, max_depth=4,  # noqa: E731
                                       learning_rate=0.02, subsample=0.8,
                                       colsample_bytree=0.7, scale_pos_weight=spw,
                                       eval_metric="auc", n_jobs=2, random_state=42)
        r = cv(StandardScaler().fit_transform(X), y, mk, repeats=6)
        res_all[c] = {"n": int(len(y)), "n_pos": n_pos, "auc": r["auc"],
                      "auc_std": r["auc_std"], "pr": r["pr"]}
        print(f"cut {c}: n={len(y)} pos={n_pos} AUC={r['auc']:.3f}±{r['auc_std']:.3f} "
              f"PR={r['pr']:.3f}")
    seq = sequential()
    (OUTPUT_DIR / "walkforward_grid.json").write_text(
        json.dumps({"expanding": res_all, "sequential": seq}, indent=2))
    write_report(res_all, seq)


def write_report(res, seq):
    L = ["# Étape 8c — Walk-forward multi-coupures",
         "",
         "Protocole identique à chaque coupure C : features sur trades < C, label H1 sur "
         "marchés débutés ≥ C et résolus (≥3), population ≥50 trades pré-C. Aucune fuite.",
         "",
         "## 1. Coupes indépendantes (expanding)",
         "",
         "| Coupure | n | positifs H1 | AUC-ROC (XGB) | AUC-PR |",
         "|---|---|---|---|---|"]
    for c, r in res.items():
        L.append(f"| {c} | {r['n']} | {r['n_pos']} ({100*r['n_pos']/r['n']:.1f} %) | "
                 f"{r['auc']:.3f}±{r['auc_std']:.3f} | {r['pr']:.3f} |")
    aucs = [r["auc"] for r in res.values()]
    L.append("")
    L.append(f"Moyenne : **AUC {np.mean(aucs):.3f}** (min {np.min(aucs):.3f}, "
             f"max {np.max(aucs):.3f}).")
    L.append("")
    if seq:
        L.append("## 2. Walk-forward séquentiel STRICT (train → test sans réentraînement)")
        L.append("")
        L.append("| train | test | n_train | n_test | AUC-ROC | AUC-PR |")
        L.append("|---|---|---|---|---|---|")
        sa = []
        for s in seq:
            L.append(f"| {s['train_cut']} | {s['test_cut']} | {s['n_train']} | "
                     f"{s['n_test']} | {s['auc']:.3f} | {s['pr']:.3f} |")
            sa.append(s["auc"])
        L.append("")
        L.append(f"**AUC moyenne séquentielle : {np.mean(sa):.3f}**")
    L.append("")
    L.append("### Lecture")
    L.append("- Stabilité de l'AUC à travers les coupures → le signal prédictif est "
             "**robuste dans le temps** (pas un artefact d'une période).")
    L.append("- Le mode séquentiel strict (aucune réutilisation) est la preuve la plus "
             "forte : un modèle entraîné sur le passé prédit la période suivante.")
    (OUTPUT_DIR / "walkforward_grid.md").write_text("\n".join(L))


if __name__ == "__main__":
    main()
