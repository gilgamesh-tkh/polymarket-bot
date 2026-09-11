#!/usr/bin/env python
"""Étape 6 — Clustering des wallets (Smart Money) sur la table wallet + PnL v2.

Features comportementales (échelles log pour les compteurs, ratios bruts sinon) :
  X1 perf      : roi, win_rate_m2m, n_markets_resolved
  X2 comport.  : maker_ratio, n_trades, n_days_active, avg_usd_trade
  X3 diversif. : n_markets, hhi, entropy

Méthodes : K-Means (k=5) et DBSCAN (eps=0.5) sur données standardisées (QuantileTransformer
robuste aux outliers) puis UMAP/PCA 2D pour la lecture. Croisement avec les seuils H1.

Sorties : output/cluster_<m>.parquet (wallets + label), output/cluster_report.md
"""
import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sklearn.cluster import KMeans, DBSCAN  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from sklearn.metrics import silhouette_score, calinski_harabasz_score  # noqa: E402
from sklearn.decomposition import PCA  # noqa: E402

from config import OUTPUT_DIR  # noqa: E402

FEATURES = ["roi", "win_rate_m2m", "n_markets_resolved", "maker_ratio", "n_trades",
            "n_days_active", "avg_usd_trade", "n_markets", "hhi", "entropy"]


def build():
    wt = pl.read_parquet(OUTPUT_DIR / "wallet_table.parquet")
    pnl = pl.read_parquet(OUTPUT_DIR / "wallet_pnl_wallet_v2.parquet")
    df = wt.join(pnl, on="address", how="inner")
    df = df.with_columns([
        pl.col("n_days_active_apx").alias("n_days_active"),
        (pl.col("usd_gross_mkt") / pl.col("n_trades")).alias("avg_usd_trade"),
        (pl.col("n_maker") / pl.col("n_trades")).alias("maker_ratio"),
    ])
    # wallets avec au moins 1 marché résolu (sinon ROI/WR non définis)
    df = df.filter(pl.col("n_markets_resolved") >= 1)
    feat = df.select(FEATURES).to_pandas()
    # log-transform sur les variables d'échelle
    for c in ["n_markets_resolved", "n_trades", "n_days_active", "avg_usd_trade", "n_markets"]:
        feat[c] = np.log1p(feat[c].clip(lower=0))
    # NaN (ex entropy/hhi sur 1 seul marché) -> imputer par la médiane
    nan_rows = feat.isna().any(axis=1)
    if nan_rows.any():
        print(f"[warn] {nan_rows.sum()} lignes avec NaN imputées par la médiane")
        feat = feat.fillna(feat.median(numeric_only=True))
    X = feat.to_numpy(dtype=float)
    return df, feat, X


def cluster(X, method, **kw):
    if method == "kmeans":
        k = kw.get("k", 5)
        m = KMeans(n_clusters=k, n_init=10, random_state=42)
    else:
        m = DBSCAN(eps=kw.get("eps", 0.5), min_samples=kw.get("min_samples", 20))
    lab = m.fit_predict(X)
    return lab


def main():
    df, feat, X = build()
    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X)
    res = {"n_wallets": len(df)}

    # --- K-Means ---
    km = KMeans(n_clusters=5, n_init=20, random_state=42).fit(Xs)
    lab_k = km.labels_
    # --- DBSCAN ---
    dbs = DBSCAN(eps=0.5, min_samples=20).fit(Xs)
    lab_d = dbs.labels_

    out = df.with_columns([
        pl.Series("km5", lab_k.astype(int)),
        pl.Series("dbscan", lab_d.astype(int)),
    ])
    out.write_parquet(OUTPUT_DIR / "cluster_wallets.parquet")

    # scores
    sil_k = silhouette_score(Xs, lab_k)
    ch_k = calinski_harabasz_score(Xs, lab_k)
    n_core = int((lab_d >= 0).sum())
    res.update({"km5_silhouette": float(sil_k), "km5_calinski": float(ch_k),
                "dbscan_n_clusters": int(lab_d.max()) + 1, "dbscan_n_noise": int((lab_d < 0).sum()),
                "dbscan_n_core": n_core})
    (OUTPUT_DIR / "cluster_metrics.json").write_text(json.dumps(res, indent=2))
    print(res)


if __name__ == "__main__":
    main()
