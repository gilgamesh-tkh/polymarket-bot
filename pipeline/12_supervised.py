#!/usr/bin/env python
"""Étape 7 — Classifieur supervisé label H1 (Smart Money).

Label : H1 = (roi > 0.20) & (win_rate_m2m > 0.65)   [~1,1 % de positifs]

Features SANS fuite : uniquement des descripteurs comportementaux/diversification
(ni roi, ni win_rate, ni pnl, ni cashflow — tout ce qui définit le label est exclu).

Modèles : RandomForest (class_weight=balanced), XGBoost (scale_pos_weight).
Évaluation : StratifiedKFold 5 × répété 5 fois → AUC-ROC, AUC-PR, précision/rappel au
meilleur F1 ; comparaison à un classifieur aléatoire (baseline AUC=0.5).

Sorties : output/supervised_report.md, output/supervised_metrics.json, modèles .joblib
"""
import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import polars as pl
import xgboost as xgb

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.metrics import (roc_auc_score, average_precision_score,  # noqa: E402
                             precision_recall_curve, f1_score)
from sklearn.model_selection import StratifiedKFold  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from config import OUTPUT_DIR  # noqa: E402

FEATS = [
    "n_trades", "maker_ratio", "avg_usd_trade", "usd_gross",
    "n_markets", "n_markets_resolved", "n_days_active", "span_days",
    "hhi", "entropy", "avg_price", "vwap",
]
LOG_FEATS = ["n_trades", "avg_usd_trade", "usd_gross", "n_markets",
             "n_markets_resolved", "n_days_active", "span_days"]


def build():
    wt = pl.read_parquet(OUTPUT_DIR / "wallet_table.parquet")
    pnl = pl.read_parquet(OUTPUT_DIR / "wallet_pnl_wallet_v2.parquet")
    df = wt.join(pnl, on="address", how="inner").filter(pl.col("n_markets_resolved") >= 1)
    df = df.with_columns([
        pl.col("n_days_active_apx").alias("n_days_active"),
        (pl.col("usd_gross_mkt") / pl.col("n_trades")).alias("avg_usd_trade"),
        (pl.col("n_maker") / pl.col("n_trades")).alias("maker_ratio"),
    ]).with_columns(
        h1=(pl.col("roi") > 0.20) & (pl.col("win_rate_m2m") > 0.65),
    )
    feat = df.select(FEATS).to_pandas()
    for c in LOG_FEATS:
        feat[c] = np.log1p(feat[c].clip(lower=0))
    X = feat.to_numpy(dtype=float)
    y = df["h1"].to_numpy().astype(int)
    # NaN -> médiane (aucun ici en théorie)
    if np.isnan(X).any():
        X = np.nan_to_num(X, nan=np.nanmedian(X))
    return df, X, y


def run_cv(X, y, model, n_splits=5, repeats=5, seed=42):
    aucs, prs = [], []
    preds = np.zeros(len(y))
    f1s, precs, recs = [], [], []
    for r in range(repeats):
        skf = StratifiedKFold(n_splits=n_splits, shuffle=True,
                              random_state=seed + r * 100)
        for tr, te in skf.split(X, y):
            m = model()
            m.fit(X[tr], y[tr])
            p = m.predict_proba(X[te])[:, 1]
            preds[te] += p / (n_splits * repeats)
            aucs.append(roc_auc_score(y[te], p))
            prs.append(average_precision_score(y[te], p))
    # seuil optimal sur F1 via preds cumulées
    prec_, rec_, th_ = precision_recall_curve(y, preds)
    f1s_ = 2 * prec_ * rec_ / (prec_ + rec_ + 1e-12)
    ib = int(np.argmax(f1s_))
    thr = th_[ib] if ib < len(th_) else 0.5
    f1 = f1_score(y, preds > thr)
    return {"auc_mean": float(np.mean(aucs)), "auc_std": float(np.std(aucs)),
            "pr_mean": float(np.mean(prs)), "pr_std": float(np.std(prs)),
            "best_f1": float(f1), "best_thr": float(thr),
            "n_pos": int(y.sum()), "n_tot": int(len(y))}, preds


def main():
    df, X, y = build()
    n_pos = int(y.sum())
    print(f"n={len(y)}  positifs H1={n_pos} ({100*n_pos/len(y):.2f}%)")

    Xs = StandardScaler().fit_transform(X)
    res = {"n": int(len(y)), "n_pos": n_pos, "features": FEATS}

    rf = lambda: RandomForestClassifier(n_estimators=300, max_depth=8,  # noqa: E731
                                        class_weight="balanced", n_jobs=2, random_state=42)
    xg = lambda: xgb.XGBClassifier(n_estimators=300, max_depth=6,  # noqa: E731
                                   learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
                                   scale_pos_weight=(len(y) - n_pos) / n_pos,
                                   eval_metric="auc", n_jobs=2, random_state=42)

    t0 = time.time()
    r_rf, p_rf = run_cv(Xs, y, rf)
    print("RF", r_rf, f"{time.time()-t0:.0f}s")
    r_xg, p_xg = run_cv(Xs, y, xg)
    print("XGB", r_xg, f"{time.time()-t0:.0f}s")

    # fit final pour importance + sauvegarde
    m_rf = rf().fit(Xs, y)
    m_xg = xg().fit(Xs, y)
    joblib.dump({"model": m_rf, "scaler": StandardScaler().fit(X)},
                OUTPUT_DIR / "model_rf.joblib")
    joblib.dump({"model": m_xg, "scaler": StandardScaler().fit(X)},
                OUTPUT_DIR / "model_xgb.joblib")

    importances = pd_sort(m_rf, m_xg)
    res.update({"rf": r_rf, "xgb": r_xg, "importances": importances})
    (OUTPUT_DIR / "supervised_metrics.json").write_text(json.dumps(res, indent=2, default=str))
    write_report(res, r_rf, r_xg, importances)
    print(json.dumps({"rf_auc": r_rf["auc_mean"], "xgb_auc": r_xg["auc_mean"]}, indent=2))


def pd_sort(m_rf, m_xg):
    import pandas as pd
    imp = pd.DataFrame({
        "feature": FEATS,
        "rf": m_rf.feature_importances_,
        "xgb": m_xg.feature_importances_,
    }).sort_values("rf", ascending=False)
    return imp.to_dict("records")


def write_report(res, r_rf, r_xg, importances):
    L = []
    L.append("# Étape 7 — Classifieur supervisé label H1 (Smart Money)")
    L.append("")
    L.append(f"Population : **{res['n']:,} wallets** (≥1 marché résolu), positifs H1 = "
             f"**{res['n_pos']} ({100*res['n_pos']/res['n']:.2f} %)**.")
    L.append("")
    L.append("Label H1 : `(roi > 0.20) & (win_rate_m2m > 0.65)`. Features **sans fuite** "
             "(aucune variable dérivée du PnL/ROI/win rate n'est utilisée) :")
    L.append("")
    L.append("`" + ", ".join(FEATS) + "`")
    L.append("")
    L.append("Évaluation : StratifiedKFold 5-fold **répété 5×** (25 splits), features "
             "standardisées. Baseline aléatoire = AUC 0,50 / AUC-PR = prévalence (1,1 %).")
    L.append("")
    L.append("| Modèle | AUC-ROC (μ±σ) | AUC-PR (μ±σ) | Meilleur F1 |")
    L.append("|---|---|---|---|")
    L.append(f"| RandomForest | {r_rf['auc_mean']:.3f}±{r_rf['auc_std']:.3f} | "
             f"{r_rf['pr_mean']:.3f}±{r_rf['pr_std']:.3f} | {r_rf['best_f1']:.3f} |")
    L.append(f"| XGBoost | {r_xg['auc_mean']:.3f}±{r_xg['auc_std']:.3f} | "
             f"{r_xg['pr_mean']:.3f}±{r_xg['pr_std']:.3f} | {r_xg['best_f1']:.3f} |")
    L.append("")
    L.append("AUC-PR d'un classifieur naïf = prévalence ≈ 1,1 % ; un bon modèle doit "
             "nettement dépasser ~0,01 en AUC-PR.")
    L.append("")
    L.append("### Importance des features (RandomForest → XGBoost)")
    L.append("")
    L.append("| feature | RF | XGB |")
    L.append("|---|---|---|")
    for r in importances:
        L.append(f"| {r['feature']} | {r['rf']:.3f} | {r['xgb']:.3f} |")
    L.append("")
    L.append("### Limites méthodologiques")
    L.append("")
    L.append("- **Cross-sectionnel** : le label H1 est calculé sur toute la fenêtre ; "
             "l'AUC mesure la *discriminabilité* (peut-on repérer un wallet rentable à "
             "partir de son comportement agrégé), PAS la *prédictibilité* (le comportement "
             "PASSE-t-il avant le résultat ?).")
    L.append("- Pour une vraie validation prédictive, il faudra un **walk-forward** "
             "(features sur [t0, t1] → label sur [t1, t2]) — étape ultérieure.")
    L.append("- Déséquilibre extrême (1,1 %) : l'AUC-ROC peut être optimiste en présence "
             "de grande variance ; l'AUC-PR est la métrique la plus informative ici.")
    (OUTPUT_DIR / "supervised_report.md").write_text("\n".join(L))


if __name__ == "__main__":
    main()
