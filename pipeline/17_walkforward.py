#!/usr/bin/env python
"""Étape 8 — Walk-forward : les features PASSÉES prédisent-elles la rentabilité FUTURE ?

Coupure C = 2025-06-30. AUCUN label passé n'est utilisé pour les features (anti-fuite) :
  - Features : agrégées sur users_sample avec timestamp < C (comportement observé AVANT C).
  - Label H1_futur : ROI>20% & WR>65% calculé sur les marchés dont le wallet a fait son
    premier trade >= C ET qui sont résolus (=> le PnL v2 de ces paires est entièrement futur).
  - Le modèle est entraîné/testé en CV sur des wallets ayant BOTH des features pré-C et un label.

Sortie : output/walkforward_report.md
"""
import datetime as dt
import json
import sys
import time
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import duckdb  # noqa: E402

from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.metrics import (average_precision_score, precision_recall_curve,  # noqa: E402
                             roc_auc_score, f1_score)
from sklearn.model_selection import StratifiedKFold  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
import xgboost as xgb  # noqa: E402

from config import OUTPUT_DIR  # noqa: E402

CUT = dt.datetime(2025, 6, 30, tzinfo=dt.timezone.utc)
CUT_EP = int(CUT.timestamp())

# Features calculables sur la fenêtre < C depuis users_sample (pas de fuite).
FEATS = ["n_trades", "maker_ratio", "avg_usd_trade", "usd_gross", "n_markets",
         "n_days", "span_days", "avg_price", "weekend_frac", "frac_buy",
         "frac_token1", "extremeness"]
LOG_FEATS = ["n_trades", "avg_usd_trade", "usd_gross", "n_markets", "span_days"]


def pre_features(mem="5GB", threads=2):
    con = duckdb.connect(config={"memory_limit": mem, "threads": threads})
    con.execute("SET enable_progress_bar=false")
    con.execute("SET temp_directory='" + str(OUTPUT_DIR.parent / ".tmp") + "'")
    t0 = time.time()
    q = f"""
    SELECT address,
           COUNT(*) AS n_trades,
           AVG(CASE WHEN role='maker' THEN 1.0 ELSE 0.0 END) AS maker_ratio,
           SUM(usd_amount) / COUNT(*) AS avg_usd_trade,
           SUM(usd_amount) AS usd_gross,
           COUNT(DISTINCT market_id) AS n_markets,
           COUNT(DISTINCT CAST(to_timestamp(timestamp) AS DATE)) AS n_days,
           (MAX(timestamp) - MIN(timestamp)) / 86400.0 AS span_days,
           AVG(price) AS avg_price,
           AVG(CASE WHEN EXTRACT(DOW FROM to_timestamp(timestamp)) IN (0,6)
                    THEN 1.0 ELSE 0.0 END) AS weekend_frac,
           AVG(CASE WHEN direction='BUY' THEN 1.0 ELSE 0.0 END) AS frac_buy,
           AVG(CASE WHEN nonusdc_side='token1' THEN 1.0 ELSE 0.0 END) AS frac_token1,
           SUM(usd_amount * ABS(price - 0.5)) / NULLIF(SUM(usd_amount), 0) AS extremeness
    FROM read_parquet('{OUTPUT_DIR/'users_sample.parquet'}')
    WHERE timestamp < {CUT_EP}
    GROUP BY address
    """
    df = con.execute(q).df()
    out = pl.from_pandas(df)
    print(f"pre_features {len(out):,} ({time.time()-t0:.0f}s)")
    return out


def build():
    feat = pre_features()
    label = pl.read_parquet(OUTPUT_DIR / "wf_label.parquet")  # n_mkts>=3
    df = feat.join(label.select(["address", "h1", "n_mkts", "pnl", "roi"]),
                   on="address", how="inner")
    df = df.filter(pl.col("n_trades") >= 100)  # comportement pré-C significatif
    feat = df.select(FEATS).to_pandas()
    for c in LOG_FEATS:
        if c in feat.columns:
            feat[c] = np.log1p(feat[c].clip(lower=0))
    X = feat.to_numpy(dtype=float)
    X = np.nan_to_num(X, nan=np.nanmedian(X, axis=0))
    y = df["h1"].to_numpy().astype(int)
    return df, X, y


def cv(X, y, model, seed=42, n_splits=5, repeats=5):
    aucs, prs, preds = [], [], np.zeros(len(y))
    for r in range(repeats):
        skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed + r * 11)
        for tr, te in skf.split(X, y):
            m = model()
            m.fit(X[tr], y[tr])
            p = m.predict_proba(X[te])[:, 1]
            preds[te] += p / (repeats * n_splits)
            aucs.append(roc_auc_score(y[te], p))
            prs.append(average_precision_score(y[te], p))
    prec, rec, th = precision_recall_curve(y, preds)
    f1s = 2 * prec * rec / (prec + rec + 1e-12)
    ib = int(np.argmax(f1s))
    return {"auc": float(np.mean(aucs)), "auc_std": float(np.std(aucs)),
            "pr": float(np.mean(prs)), "pr_std": float(np.std(prs)),
            "best_f1": float(f1_score(y, preds > th[ib])),
            "n": int(len(y)), "n_pos": int(y.sum())}


def main():
    t0 = time.time()
    df, X, y = build()
    n_pos = int(y.sum())
    print(f"population WF: n={len(y)}, positifs H1 futur={n_pos} ({100*n_pos/len(y):.2f}%)")
    Xs = StandardScaler().fit_transform(X)
    spw = (len(y) - n_pos) / n_pos

    mk_rf = lambda: RandomForestClassifier(n_estimators=400, max_depth=6,  # noqa: E731
                                           class_weight="balanced", n_jobs=2, random_state=42)
    mk_xg = lambda: xgb.XGBClassifier(n_estimators=400, max_depth=5,  # noqa: E731
                                      learning_rate=0.03, subsample=0.8, colsample_bytree=0.7,
                                      scale_pos_weight=spw, eval_metric="auc",
                                      n_jobs=2, random_state=42)
    r_rf = cv(Xs, y, mk_rf)
    r_xg = cv(Xs, y, mk_xg)
    print("RF", {k: round(v, 4) for k, v in r_rf.items() if isinstance(v, float)})
    print("XGB", {k: round(v, 4) for k, v in r_xg.items() if isinstance(v, float)})
    print(f"({time.time()-t0:.0f}s)")

    res = {"cut": str(CUT.date()), "rf": r_rf, "xgb": r_xg, "features": FEATS}
    (OUTPUT_DIR / "walkforward_metrics.json").write_text(json.dumps(res, indent=2))
    write_report(res)
    return res


def write_report(res):
    L = []
    L.append("# Étape 8 — Walk-forward : le passé prédit-il le futur ?")
    L.append("")
    L.append(f"**Coupure** : trades < `{res['cut']}` pour les features ; label = H1 "
             "(ROI>20 % & WinRate>65 %) sur les marchés débutés après la coupure et résolus.")
    L.append("")
    L.append("### Résultat")
    L.append("")
    L.append("| Modèle | AUC-ROC | AUC-PR | F1 max |")
    L.append("|---|---|---|---|")
    L.append(f"| RandomForest | {res['rf']['auc']:.3f}±{res['rf']['auc_std']:.3f} | "
             f"{res['rf']['pr']:.3f} | {res['rf']['best_f1']:.3f} |")
    L.append(f"| XGBoost | {res['xgb']['auc']:.3f}±{res['xgb']['auc_std']:.3f} | "
             f"{res['xgb']['pr']:.3f} | {res['xgb']['best_f1']:.3f} |")
    L.append("")
    L.append(f"Population : **{res['rf']['n']:,} wallets** (comportement ≥100 trades avant "
             f"coupure ET ≥3 marchés résolus après), dont **{res['rf']['n_pos']} positifs H1 "
             f"futurs ({100*res['rf']['n_pos']/res['rf']['n']:.1f} %)**.")
    L.append("")
    L.append("### Comparaison avec la discrimination (étape 7e)")
    L.append("")
    L.append("- Discrimination (label et features sur la même période) : AUC-ROC ≈ **0,93**")
    L.append("- **Walk-forward (features passées → label futur) : AUC-ROC ≈ "
             f"{res['xgb']['auc']:.2f}**")
    L.append("")
    L.append("L'écart mesure la **part de signal réellement prédictif** vs la part qui vient "
             "de la contemporanéité (comportement et résultat mesurés ensemble).")
    L.append("")
    (OUTPUT_DIR / "walkforward_report.md").write_text("\n".join(L))


if __name__ == "__main__":
    main()
