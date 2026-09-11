#!/usr/bin/env python
"""Étape 9-H3 — Analyse : les pics de volume anormaux prédisent-ils un mouvement de prix ?

Série horaire par marché (h3_hourly) triée dans le temps.
Anomalie vs passé : médiane/MAD glissantes des 24 heures PRÉCÉDENTES (rolling + shift 1).
Longshot : prix horaire < 0.05 ou > 0.95. Mouvement : |Δprix| max dans les 24 rangs suivants.

Test : P(Δ>15%|anomalie & longshot) vs P(Δ>15%|pas anomalie & longshot).

Sortie : output/h3_analysis.parquet, output/h3_report.md
"""
import sys
import time
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import OUTPUT_DIR  # noqa: E402


def run():
    t0 = time.time()
    df = pl.read_parquet(OUTPUT_DIR / "h3_hourly.parquet")
    print(f"rows {len(df):,} marchés {df['market_id'].n_unique():,}")

    df = df.sort(["market_id", "hour_ts"]).with_columns(
        idx=pl.int_range(pl.len()).over("market_id"))
    df = df.sort(["market_id", "idx"])

    # --- volume baseline passée (médiane & MAD des 24 rangs précédents) ---
    df = df.with_columns([
        pl.col("vol_usd").rolling_median(window_size=24, min_samples=6)
        .over("market_id", mapping_strategy="group_to_rows").alias("med24"),
        pl.col("vol_usd").rolling_std(window_size=24, min_samples=6)
        .over("market_id", mapping_strategy="group_to_rows").alias("std24"),
    ]).with_columns([
        pl.col("med24").shift(1).over("market_id", mapping_strategy="group_to_rows").alias("base"),
        pl.col("std24").shift(1).over("market_id", mapping_strategy="group_to_rows").alias("sd"),
    ])
    df = df.with_columns(
        ratio=pl.col("vol_usd") / pl.col("base").replace(0, None),
    ).with_columns(
        anomaly=(pl.col("ratio") >= 5.0) & (pl.col("vol_usd") >= 200)
        & pl.col("base").is_not_null(),
        longshot=(pl.col("avg_price") < 0.05) | (pl.col("avg_price") > 0.95),
    )

    # --- mouvement dans les 24 prochains rangs (futur min/max) ---
    df = df.with_columns([
        pl.col("avg_price").rolling_min(window_size=25, min_samples=1)
        .over("market_id", mapping_strategy="group_to_rows").alias("fut_min_all"),
        pl.col("avg_price").rolling_max(window_size=25, min_samples=1)
        .over("market_id", mapping_strategy="group_to_rows").alias("fut_max_all"),
    ]).with_columns([
        pl.col("fut_min_all").shift(-24).over("market_id", mapping_strategy="group_to_rows").alias("fut_min"),
        pl.col("fut_max_all").shift(-24).over("market_id", mapping_strategy="group_to_rows").alias("fut_max"),
    ]).with_columns(
        move_24h=pl.max_horizontal(
            [(pl.col("avg_price") - pl.col("fut_min")).abs(),
             (pl.col("fut_max") - pl.col("avg_price")).abs()]),
    ).with_columns(price_move_gt15=pl.col("move_24h") > 0.15)
    df = df.drop(["fut_min_all", "fut_max_all"])
    df.write_parquet(OUTPUT_DIR / "h3_analysis.parquet")

    # --- stats ---
    L = []
    p = L.append
    p("# Étape 9-H3 — Anomalies de volume → mouvements de prix (longshots)")
    p("")
    p(f"Marchés : résolus binaires 2025, volume 1-50k$ "
      f"({df['market_id'].n_unique():,}). Heures-marchés : {len(df):,}. "
      f"Anomalies détectées : {int(df['anomaly'].sum()):,}.")
    p("")
    p("### Définitions")
    p("- **Anomalie** : volume horaire ≥ 5× médiane des 24 h précédentes ET ≥ 200 $.")
    p("- **Longshot** : prix moyen horaire < 0,05 ou > 0,95 (prob. implicite < 5 %).")
    p("- **Mouvement** : |Δprix| maximal dans les 24 rangs horaires suivants > 0,15.")
    p("")
    ls = df.filter(pl.col("longshot"))
    base = ls.filter(~pl.col("anomaly"))
    anom = ls.filter(pl.col("anomaly"))
    p("### Résultats (heures longshot)")
    p("")
    p("| Groupe | n | P(Δ>15% en 24h) | médiane \|Δ\| |")
    p("|---|---|---|---|")
    for name, sub in [("longshot (tous)", ls), ("sans anomalie (baseline)", base),
                      ("**avec anomalie**", anom)]:
        if len(sub) == 0:
            p(f"| {name} | 0 | - | - |")
            continue
        rate = sub["price_move_gt15"].mean()
        p(f"| {name} | {len(sub):,} | **{100*rate:.1f} %** | {sub['move_24h'].median():.3f} |")
    p("")
    if len(anom) > 50 and len(base) > 50:
        from scipy import stats
        t, pv = stats.ttest_ind(anom["move_24h"].drop_nulls().to_numpy(),
                                base["move_24h"].drop_nulls().to_numpy(), equal_var=False)
        p(f"Test t de Welch (|Δ| anomalie vs baseline) : t={t:.2f}, p={pv:.2e}")
        p("")
        p("### Lecture pour H3")
        p("Si P(Δ>15%|anomalie) > P(Δ>15%|baseline), l'anomalie de volume **précède** un "
          "mouvement de prix plus fréquent → H3 soutenue. Sinon, l'anomalie ne prédit pas "
          "le mouvement (le volume suit le prix plutôt qu'il ne le précède).")
    p("")
    p("### Limites")
    p("- Heures sans trade absentes de la série → '24 rangs' ≈ 24 h effectives, pas "
      "calendaires.")
    p("- Le prix est en perspective YES ; les deux extrêmes (<0,05 ou >0,95) couvrent les "
      "deux côtés, mais le mouvement est mesuré sur le prix YES uniquement.")
    p("- Seuils (×5, 200 $, 0,15) arbitraires mais documentés ; une analyse de sensibilité "
      "est possible.")
    (OUTPUT_DIR / "h3_report.md").write_text("\n".join(L))
    print("\n".join(L))
    print(f"done {time.time()-t0:.0f}s")


if __name__ == "__main__":
    run()
