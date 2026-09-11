#!/usr/bin/env python
"""Étape 7c — Classifieur enrichi label H1 (features comportementales étendues).

Combine : features étape 7 (12) + features avancées (13_features_adv) :
  weekend_frac, hour_entropy, size_cv, extremeness, frac_token1,
  mkt_vol_med, mkt_negrisk_share, mkt_horizon_days_med
+ RandomSearch léger XGBoost. CV StratifiedKFold 5×5. AUC-ROC / AUC-PR.

Sortie : output/supervised_v2_report.md
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import polars as pl
import xgboost as xgb

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.metrics import (average_precision_score, f1_score,  # noqa: E402
                             precision_recall_curve, roc_auc_score)
from sklearn.model_selection import StratifiedKFold  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from config import OUTPUT_DIR  # noqa: E402

BASE_FEATS = ["n_trades", "maker_ratio", "avg_usd_trade", "usd_gross",
              "n_markets", "n_markets_resolved", "n_days_active", "span_days",
              "hhi", "entropy", "avg_price", "vwap"]
ADV_FEATS = ["weekend_frac", "hour_entropy", "size_cv", "extremeness",
             "frac_token1", "mkt_vol_med", "mkt_negrisk_share", "mkt_horizon_days_med"]
ABC_FEATS = ["first_ts", "n_weeks_ratio", "price_range", "entry_timing_s",
             "time_to_end_s", "dominant_hour_share", "trades_per_market",
             "roundtrip_share", "side_imbalance", "mkt_impact_avg", "mkt_impact_med",
             "arbitrage_share", "buy_px_tok1", "sell_px_tok1", "buy_sell_gap_tok1",
             "buy_px_tok2", "sell_px_tok2", "buy_sell_gap_tok2",
             "cat_sports_share", "cat_crypto_share", "cat_politics_share"]
NET_FEATS = ["deg_total", "strength_total", "edges_total", "recurrent_total",
             "recurrence", "recip", "avg_edge_usd"]
INTER_FEATS = ["inter_mm", "inter_conc", "inter_side_lowpx", "inter_scale",
               "inter_freq_days", "inter_trades_mkts"]
LOG_FEATS = ["n_trades", "avg_usd_trade", "usd_gross", "n_markets",
             "n_markets_resolved", "n_days_active", "span_days",
             "mkt_vol_med", "mkt_horizon_days_med", "price_range",
             "trades_per_market", "mkt_impact_avg", "mkt_impact_med",
             "deg_total", "strength_total", "edges_total"]


def build(use_adv=True, use_abc=True, use_net=True, use_inter=True):
    wt = pl.read_parquet(OUTPUT_DIR / "wallet_table.parquet")
    pnl = pl.read_parquet(OUTPUT_DIR / "wallet_pnl_wallet_v2.parquet")
    adv = pl.read_parquet(OUTPUT_DIR / "wallet_features_adv.parquet")
    abc = pl.read_parquet(OUTPUT_DIR / "wallet_features_abc.parquet")
    net = pl.read_parquet(OUTPUT_DIR / "wallet_network.parquet")
    df = wt.join(pnl, on="address", how="inner").join(adv, on="address", how="inner")
    df = df.join(abc.drop("address_right") if "address_right" in abc.columns
                 else abc, on="address", how="inner")
    df = df.join(net.drop("address_right") if "address_right" in net.columns
                 else net, on="address", how="inner")
    df = df.filter(pl.col("n_markets_resolved") >= 1)
    df = df.with_columns([
        pl.col("n_days_active_apx").alias("n_days_active"),
        (pl.col("usd_gross_mkt") / pl.col("n_trades")).alias("avg_usd_trade"),
        (pl.col("n_maker") / pl.col("n_trades")).alias("maker_ratio"),
    ]).with_columns(
        h1=(pl.col("roi") > 0.20) & (pl.col("win_rate_m2m") > 0.65),
        # interactions métier (avant log) : croisements interprétables
        inter_mm=(pl.col("n_maker") / pl.col("n_trades")) * pl.col("roundtrip_share").fill_null(0),
        inter_conc=pl.col("hhi") * pl.col("n_markets_resolved").fill_null(0),
        inter_side_lowpx=(pl.col("frac_token1").fill_null(0.5)
                          * (1 - pl.col("avg_price").fill_null(0.5))),
        inter_scale=pl.col("usd_gross") * (pl.col("usd_gross") / pl.col("n_trades")).fill_null(0),
        inter_freq_days=(pl.col("n_trades") / pl.col("n_days_active_apx")).fill_null(0),
        inter_trades_mkts=(pl.col("n_trades") / pl.col("n_markets_resolved").clip(lower_bound=1)),
    )
    feats = (BASE_FEATS + (ADV_FEATS if use_adv else []) + (ABC_FEATS if use_abc else [])
             + (NET_FEATS if use_net else []) + (INTER_FEATS if use_inter else []))
    feat = df.select(feats).to_pandas()
    for c in LOG_FEATS:
        if c in feat.columns:
            feat[c] = np.log1p(feat[c].clip(lower=0))
    # first_ts -> âge en années (depuis le début du dataset)
    if "first_ts" in feat.columns:
        feat["first_ts"] = (1669060169 - feat["first_ts"]) / (365 * 86400)
    X = feat.to_numpy(dtype=float)
    X = np.nan_to_num(X, nan=np.nanmedian(X, axis=0))
    y = df["h1"].to_numpy().astype(int)
    return df, X, y, feats


def cv_eval(X, y, model, seed=42, repeats=5, n_splits=5):
    aucs, prs = [], []
    preds = np.zeros(len(y))
    for r in range(repeats):
        skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed + r * 97)
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
    thr = th[ib] if ib < len(th) else 0.5
    return {"auc_mean": float(np.mean(aucs)), "auc_std": float(np.std(aucs)),
            "pr_mean": float(np.mean(prs)), "pr_std": float(np.std(prs)),
            "best_f1": float(f1_score(y, preds > thr)), "best_thr": float(thr)}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--abc", action="store_true", help="inclure features A+B+C")
    ap.add_argument("--net", action="store_true", help="inclure features réseau X4")
    ap.add_argument("--inter", action="store_true", help="inclure interactions")
    ap.add_argument("--no-adv", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    df, X, y, feats = build(use_adv=not a.no_adv, use_abc=a.abc,
                            use_net=a.net, use_inter=a.inter)
    n_pos = int(y.sum())
    print(f"n={len(y)} pos={n_pos} ({100*n_pos/len(y):.2f}%) feats={len(feats)}")
    Xs = StandardScaler().fit_transform(X)

    res = {"n": int(len(y)), "n_pos": n_pos, "n_feats": len(feats),
           "base_feats": BASE_FEATS, "adv_feats": ADV_FEATS if not a.no_adv else [],
           "abc_feats": ABC_FEATS if a.abc else [],
           "net_feats": NET_FEATS if a.net else [],
           "inter_feats": INTER_FEATS if a.inter else []}

    # XGBoost avec scale_pos_weight ; petit RandomSearch manuel sur 3 combos
    spw = (len(y) - n_pos) / n_pos
    combos = [
        dict(n_estimators=400, max_depth=5, learning_rate=0.03, subsample=0.8,
             colsample_bytree=0.7, min_child_weight=3, reg_lambda=2),
        dict(n_estimators=500, max_depth=4, learning_rate=0.02, subsample=0.9,
             colsample_bytree=0.6, min_child_weight=5, reg_lambda=3),
        dict(n_estimators=600, max_depth=6, learning_rate=0.05, subsample=0.7,
             colsample_bytree=0.8, min_child_weight=2, reg_lambda=1),
    ]
    best = None
    for cfg in combos:
        mk = lambda c=cfg: xgb.XGBClassifier(  # noqa: E731
            eval_metric="auc", scale_pos_weight=spw, n_jobs=2, random_state=42, **c)
        m = cv_eval(Xs, y, mk)
        print("combo", cfg["max_depth"], "auc", round(m["auc_mean"], 4),
              "pr", round(m["pr_mean"], 4))
        if best is None or m["auc_mean"] > best[1]["auc_mean"]:
            best = (cfg, m)

    cfg, m_xgb = best
    res["xgb_best_combo"] = cfg
    res["xgb"] = m_xgb

    # RF référence (avec features étendues)
    rf = lambda: RandomForestClassifier(n_estimators=400, max_depth=8,  # noqa: E731
                                        class_weight="balanced", n_jobs=2, random_state=42)
    m_rf = cv_eval(Xs, y, rf)
    res["rf"] = m_rf

    # modèle final + importance
    fin = xgb.XGBClassifier(eval_metric="auc", scale_pos_weight=spw, n_jobs=2,
                            random_state=42, **cfg).fit(Xs, y)
    imp = sorted(zip(feats, fin.feature_importances_), key=lambda t: -t[1])
    res["importances"] = [{"feature": f, "xgb": float(v)} for f, v in imp]
    imp_dict = [{"feature": f, "xgb": float(v)} for f, v in imp]

    (OUTPUT_DIR / "supervised_v2_metrics.json").write_text(
        json.dumps(res, indent=2, default=str))
    write_report(res, m_rf, m_xgb, imp_dict, feats)
    print(f"RF auc={m_rf['auc_mean']:.4f} pr={m_rf['pr_mean']:.4f} | "
          f"XGB auc={m_xgb['auc_mean']:.4f} pr={m_xgb['pr_mean']:.4f} "
          f"({time.time()-t0:.0f}s)")


def write_report(res, r_rf, r_xg, imp, feats):
    L = []
    L.append("# Étape 7c — Classifieur enrichi label H1")
    L.append("")
    L.append(f"Population **{res['n']:,} wallets**, positifs H1 **{res['n_pos']} "
             f"({100*res['n_pos']/res['n']:.2f} %)**. Features : 12 de base + 8 avancées "
             f"(profil temporel, sélection de marchés) — {res['n_feats']} au total, aucune fuite.")
    L.append("")
    L.append("| Modèle | AUC-ROC | AUC-PR | F1 max |")
    L.append("|---|---|---|---|")
    L.append(f"| RandomForest (v2) | {r_rf['auc_mean']:.3f}±{r_rf['auc_std']:.3f} | "
             f"{r_rf['pr_mean']:.3f} | {r_rf['best_f1']:.3f} |")
    L.append(f"| XGBoost (v2, best) | {r_xg['auc_mean']:.3f}±{r_xg['auc_std']:.3f} | "
             f"{r_xg['pr_mean']:.3f} | {r_xg['best_f1']:.3f} |")
    L.append("")
    L.append("Rappel étape 7 : RF AUC 0,895 / XGB 0,888 ; AUC-PR RF 0,138 / XGB 0,172.")
    L.append("")
    L.append("### Top features (XGBoost)")
    L.append("")
    L.append("| feature | importance | | feature | importance |")
    L.append("|---|---|---|---|---|")
    rows = imp
    half = (len(rows) + 1) // 2
    for i in range(half):
        l = rows[i]
        r = rows[i + half] if i + half < len(rows) else None
        ls = f"| {l['feature']} | {l['xgb']:.3f} |"
        rs = f"| {r['feature']} | {r['xgb']:.3f} |" if r else "| | |"
        L.append(ls + " " + rs)
    L.append("")
    (OUTPUT_DIR / "supervised_v2_report.md").write_text("\n".join(L))


if __name__ == "__main__":
    main()
