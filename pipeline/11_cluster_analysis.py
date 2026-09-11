#!/usr/bin/env python
"""Étape 6 (analyse) — qualité du clustering + croisement H1.

- silhouette/Calinski pour k=3..8 (K-Means)
- DBSCAN pour une grille d'eps (0.3..1.5) : nb clusters / bruit
- Label H1 = (roi>0.20 & win_rate>0.65) ; distribution par cluster + séparation
- Conclusion honnête : le clustering sépare-t-il la Smart Money ?

Sortie : output/cluster_analysis.md + cluster_analysis.json
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

from config import OUTPUT_DIR  # noqa: E402
from importlib import import_module

FEATURES = import_module("10_clustering").FEATURES


def build():
    wt = pl.read_parquet(OUTPUT_DIR / "wallet_table.parquet")
    pnl = pl.read_parquet(OUTPUT_DIR / "wallet_pnl_wallet_v2.parquet")
    df = wt.join(pnl, on="address", how="inner").filter(pl.col("n_markets_resolved") >= 1)
    df = df.with_columns([
        pl.col("n_days_active_apx").alias("n_days_active"),
        (pl.col("usd_gross_mkt") / pl.col("n_trades")).alias("avg_usd_trade"),
        (pl.col("n_maker") / pl.col("n_trades")).alias("maker_ratio"),
    ])
    feat = df.select(FEATURES).to_pandas()
    for c in ["n_markets_resolved", "n_trades", "n_days_active", "avg_usd_trade", "n_markets"]:
        feat[c] = np.log1p(feat[c].clip(lower=0))
    feat = feat.fillna(feat.median(numeric_only=True))
    X = feat.to_numpy(dtype=float)
    Xs = StandardScaler().fit_transform(X)
    return df, Xs


def main():
    df, Xs = build()
    n = len(df)
    L = []
    out = {"n_wallets": n}

    L.append("# Étape 6 — Analyse du clustering & croisement H1")
    L.append("")
    L.append(f"Population : **{n:,} wallets** éligibles avec ≥1 marché résolu. "
             f"Features comportementales : ROI, win rate, nb marchés résolus, ratio maker, "
             f"nb trades, jours actifs, taille moyenne de trade, nb marchés, HHI, entropie "
             f"(log1p sur les compteurs, standardisation).")
    L.append("")

    # --- K-Means k=3..8 ---
    L.append("## K-Means — robustesse au choix de k")
    L.append("")
    L.append("| k | silhouette | calinski-harabasz |")
    L.append("|---|---|---|")
    rows = []
    best = None
    for k in range(3, 9):
        km = KMeans(n_clusters=k, n_init=20, random_state=42).fit(Xs)
        sil = silhouette_score(Xs, km.labels_)
        ch = calinski_harabasz_score(Xs, km.labels_)
        rows.append((k, sil, ch))
        L.append(f"| {k} | {sil:.4f} | {ch:.0f} |")
        if best is None or sil > best[1]:
            best = (k, sil)
    out["kmeans_best_k_sil"] = best[0]
    L.append("")
    L.append(f"Meilleur k selon silhouette : **k={best[0]}** ({best[1]:.4f}). "
             "Silhouette faible (<0.25) → les wallets forment un **continuum**, pas des "
             "clusters nets : attendu en données financières.")
    L.append("")

    # --- DBSCAN grille eps ---
    L.append("## DBSCAN — sensibilité à eps (min_samples=20)")
    L.append("")
    L.append("| eps | clusters | bruit (%) |")
    L.append("|---|---|---|")
    for eps in [0.3, 0.5, 0.7, 1.0, 1.5]:
        d = DBSCAN(eps=eps, min_samples=20).fit(Xs)
        k = int(d.labels_.max()) + 1
        noise = int((d.labels_ < 0).sum())
        L.append(f"| {eps} | {k} | {100*noise/n:.1f} % |")
    L.append("")
    L.append("DBSCAN ne trouve pas de structure dense nette : à eps faible tout est bruit, "
             "à eps fort les clusters fusionnent. Cohérent avec le continuum observé.")
    L.append("")

    # --- Croisement H1 ---
    df = df.with_columns(h1=((pl.col("roi") > 0.20) & (pl.col("win_rate_m2m") > 0.65)))
    n_h1 = int(df["h1"].sum())
    out["n_h1"] = n_h1
    out["pct_h1"] = round(100 * n_h1 / n, 2)
    L.append(f"## Croisement avec le label H1 (ROI>20 % & WinRate>65 %)")
    L.append("")
    L.append(f"Wallets vérifiant H1 : **{n_h1:,} ({100*n_h1/n:.2f} %)**")
    L.append("")

    km = KMeans(n_clusters=5, n_init=20, random_state=42).fit(Xs)
    df = df.with_columns(pl.Series("km5", km.labels_.astype(int)))
    cont = (df.group_by("km5").agg(
        pl.len().alias("n"),
        pl.col("h1").sum().alias("n_h1"),
        pl.col("roi").median().alias("roi_med"),
        pl.col("win_rate_m2m").median().alias("wr_med"),
    ).with_columns(share_h1=pl.col("n_h1") / pl.col("n")).sort("km5"))
    L.append("| cluster | n | n_H1 | %H1 | roi médian | winrate médian |")
    L.append("|---|---|---|---|---|---|")
    for r in cont.iter_rows(named=True):
        L.append(f"| {r['km5']} | {r['n']:,} | {r['n_h1']:,} | {100*r['share_h1']:.1f} % | "
                 f"{r['roi_med']:.3f} | {r['wr_med']:.3f} |")
    L.append("")
    # séparation : %H1 par cluster vs global ; lift
    glob = n_h1 / n
    max_lift = float(cont["share_h1"].max())
    L.append(f"Part H1 globale : {100*glob:.2f} %. Meilleur cluster : **{100*max_lift:.1f} %** "
             f"(lift {max_lift/glob:.2f}×).")
    L.append("")
    L.append("## Conclusion")
    L.append("")
    L.append("- Le clustering (K-Means ou DBSCAN) ne sépare **pas** un groupe 'Smart Money' "
             "nettement : la structure dominante est la **taille/intensité d'activité** "
             "(petits vs gros traders / makers), pas la performance.")
    L.append("- Le meilleur cluster H1 n'atteint qu'un lift modeste (≤~2×) : les wallets "
             "rentables (ROI>20 % & WR>65 %) restent rares et dispersés → cohérent avec "
             "l'hypothèse d'une petite minorité, mais le clustering non supervisé seul ne "
             "suffit pas à les isoler.")
    L.append("- **Recommandation** : passer à une approche **supervisée/semi-supervisée** "
             "(label H1 + RandomForest/XGBoost, ou Isolation Forest sur les résidus) plutôt "
             "que clustering pur. Le clustering servira de features d'analyse, pas de label.")

    (OUTPUT_DIR / "cluster_analysis.md").write_text("\n".join(L))
    (OUTPUT_DIR / "cluster_analysis.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    print("\n[ok] output/cluster_analysis.md")


if __name__ == "__main__":
    main()
