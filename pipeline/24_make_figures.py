#!/usr/bin/env python
"""Génère les figures du mémoire dans latex/figures/.

- fig_h1_auc_discrimination.png : AUC-ROC discrimination (RF/XGB), échantillon H1
- fig_h1_walkforward.png       : AUC walk-forward par coupure (barres)
- fig_pnl_distribution.png     : distribution du PnL/ROI/winrate wallets (2 panneaux)
- fig_feature_importance.png   : top features XGBoost (jeu final)
- fig_h2_reciprocity.png       : volume réciproque vs wash suspect (H2)
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import xgboost as xgb

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.metrics import (average_precision_score, roc_auc_score,  # noqa: E402
                             roc_curve, precision_recall_curve)
from sklearn.model_selection import StratifiedKFold  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "latex" / "figures"
OUT.mkdir(exist_ok=True)
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# import du build du classifieur v2 (discrimination, jeu complet 7d+X4)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import importlib.util  # noqa: E402
spec = importlib.util.spec_from_file_location("m14", OUTPUT_DIR.parent / "14_supervised_v2.py")
m14 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m14)


def fig_discrimination():
    df, X, y, feats = m14.build(use_adv=True, use_abc=True, use_net=True, use_inter=False)
    Xs = StandardScaler().fit_transform(X)
    n_pos = int(y.sum())
    spw = (len(y) - n_pos) / n_pos
    models = {
        "RandomForest": RandomForestClassifier(n_estimators=400, max_depth=8,
                                               class_weight="balanced", n_jobs=2,
                                               random_state=42),
        "XGBoost": xgb.XGBClassifier(n_estimators=500, max_depth=5, learning_rate=0.03,
                                     subsample=0.8, colsample_bytree=0.7,
                                     scale_pos_weight=spw, eval_metric="auc",
                                     n_jobs=2, random_state=42),
    }
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    fig, ax = plt.subplots(1, 1, figsize=(5.6, 4.6))
    for name, mk in models.items():
        tprs, aucs, base = [], [], 0.0
        mean_fpr = np.linspace(0, 1, 200)
        for tr, te in skf.split(Xs, y):
            m = mk
            from sklearn.base import clone
            m = clone(mk).fit(Xs[tr], y[tr])
            p = m.predict_proba(Xs[te])[:, 1]
            fpr, tpr, _ = roc_curve(y[te], p)
            aucs.append(roc_auc_score(y[te], p))
            tprs.append(np.interp(mean_fpr, fpr, tpr))
            tprs[-1][0] = 0.0
        mean_tpr = np.mean(tprs, axis=0)
        mean_tpr[-1] = 1.0
        ax.plot(mean_fpr, mean_tpr, label=f"{name} (AUC={np.mean(aucs):.3f})", lw=2)
    ax.plot([0, 1], [0, 1], "k--", lw=1, label="Aléatoire (0.50)")
    ax.set_xlabel("Taux de faux positifs"); ax.set_ylabel("Taux de vrais positifs")
    ax.set_title("Discrimination du label H1 (CV 5 plis)")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "fig_h1_auc_discrimination.png", dpi=200)
    plt.close(fig)
    print("fig_discrimination ok")


def fig_walkforward():
    data = json.loads((OUTPUT_DIR / "walkforward_grid.json").read_text())
    exp = data.get("expanding", data)
    cuts = list(exp.keys())
    aucs = [exp[c]["auc"] for c in cuts]
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    bars = ax.bar([c[5:].replace("-", "/") for c in cuts], aucs,
                  color="#4C72B0", alpha=0.85)
    ax.axhline(np.mean(aucs), color="crimson", ls="--", lw=1.2,
               label=f"Moyenne = {np.mean(aucs):.3f}")
    for b, v in zip(bars, aucs):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.008, f"{v:.2f}",
                ha="center", fontsize=9)
    ax.set_ylim(0.5, 1.0)
    ax.set_ylabel("AUC-ROC (walk-forward)")
    ax.set_xlabel("Coupure temporelle")
    ax.set_title("Walk-forward : le comportement passé prédit le futur")
    ax.legend(fontsize=8); ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "fig_h1_walkforward.png", dpi=200)
    plt.close(fig)
    print("fig_walkforward ok")


def fig_distributions():
    w = pl.read_parquet(OUTPUT_DIR / "wallet_pnl_wallet_v2.parquet")
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.4))
    # PnL (clip pour lisibilité)
    pnl = w["pnl"].clip(-5000, 5000).to_numpy()
    axes[0].hist(pnl, bins=60, color="#55A868", alpha=0.85)
    axes[0].axvline(0, color="k", lw=1)
    axes[0].set_title("PnL par wallet ($, fenêtré ±5k)")
    axes[0].set_xlabel("PnL"); axes[0].set_ylabel("wallets")
    # ROI
    roi = w["roi"].drop_nulls().clip(-1, 1).to_numpy()
    axes[1].hist(roi, bins=60, color="#C44E52", alpha=0.85)
    axes[1].axvline(0.20, color="k", ls="--", lw=1, label="Seuil H1")
    axes[1].set_title("ROI par wallet"); axes[1].set_xlabel("ROI")
    axes[1].legend(fontsize=8)
    # win rate
    wr = w["win_rate_m2m"].drop_nulls().to_numpy()
    axes[2].hist(wr, bins=60, color="#4C72B0", alpha=0.85)
    axes[2].axvline(0.65, color="k", ls="--", lw=1, label="Seuil H1")
    axes[2].set_title("Win rate (marchés résolus)")
    axes[2].set_xlabel("Win rate"); axes[2].legend(fontsize=8)
    for a in axes:
        a.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "fig_pnl_distribution.png", dpi=200)
    plt.close(fig)
    print("fig_distributions ok")


def fig_importance():
    j = json.loads((OUTPUT_DIR / "supervised_v2_metrics.json").read_text())
    imp = j["importances"][:12]
    feats = [i["feature"] for i in imp][::-1]
    vals = [i["xgb"] for i in imp][::-1]
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    ax.barh(feats, vals, color="#4C72B0")
    ax.set_xlabel("Importance (XGBoost)")
    ax.set_title("Top 12 features prédictives du label H1")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "fig_feature_importance.png", dpi=200)
    plt.close(fig)
    print("fig_importance ok")


def fig_h2():
    pairs = pl.read_parquet(OUTPUT_DIR / "h2_pairs.parquet")
    recip = pairs.filter(pl.col("is_reciprocal"))
    susp = recip.filter((pl.col("usd_both") >= 10000) & (pl.col("n_both") >= 20))
    tot = pairs["usd_both"].sum()
    # self-trade: filtré dès l'extraction (2 edges ~0), on le force à ~0 pour l'affichage
    labels = ["Auto-échange\n(maker=taker)", "Pairs réciproques\n(large)",
              "Wash suspect\n(seuils stricts)"]
    vals = [0.0, recip["usd_both"].sum(), susp["usd_both"].sum()]
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    bars = ax.bar(labels, [v / tot * 100 for v in vals],
                  color=["#C44E52", "#DD8452", "#4C72B0"])
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.4,
                f"{v/tot*100:.1f}%" if v > 0 else "<0,01%", ha="center", fontsize=9)
    ax.set_ylabel("Part du volume total (%)")
    ax.set_title("H2 — volume impliqué dans les échanges suspects")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "fig_h2_reciprocity.png", dpi=200)
    plt.close(fig)
    print("fig_h2 ok")


if __name__ == "__main__":
    fig_discrimination()
    fig_walkforward()
    fig_distributions()
    fig_importance()
    fig_h2()
    print("figures ->", OUT)
