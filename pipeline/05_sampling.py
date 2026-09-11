#!/usr/bin/env python
"""Étape 4 — Échantillonnage stratifié des wallets éligibles.

Strates par volume usd_gross : Low <10k$, Medium [10k, 100k[, High >=100k$.
n = 10 000 wallets, répartis proportionnellement à l'effectif de chaque strate.
Graine fixe pour la reproductibilité. Sortie : wallet_sample.parquet (+ résumé).

Usage : python 05_sampling.py [--n 10000] [--seed 42]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import polars as pl  # noqa: E402

from config import OUTPUT_DIR  # noqa: E402

LOW = 10_000.0
HIGH = 100_000.0


def main(n=10000, seed=42):
    df = pl.read_parquet(OUTPUT_DIR / "wallet_eligible.parquet")
    df = df.with_columns(
        pl.when(pl.col("usd_gross") < LOW).then(pl.lit("Low"))
        .when(pl.col("usd_gross") < HIGH).then(pl.lit("Medium"))
        .otherwise(pl.lit("High"))
        .alias("stratum")
    )
    sizes = df.group_by("stratum").len().sort("stratum")
    total = len(df)

    # répartition proportionnelle (au moins 1 par strate non vide)
    alloc = {r["stratum"]: max(1, round(n * r["len"] / total)) for r in sizes.iter_rows(named=True)}
    # ajustement pour atteindre exactement n
    diff = n - sum(alloc.values())
    strata_sorted = [r["stratum"] for r in sizes.iter_rows(named=True)]
    if diff != 0:
        order = strata_sorted if diff > 0 else list(reversed(strata_sorted))
        for s in order:
            if diff == 0:
                break
            alloc[s] += 1 if diff > 0 else -1
            alloc[s] = max(0, alloc[s])
            diff += -1 if diff > 0 else 1

    frames = []
    for s in strata_sorted:
        if alloc[s] <= 0:
            continue
        sub = df.filter(pl.col("stratum") == s)
        k = min(alloc[s], len(sub))
        frames.append(sub.sample(n=k, shuffle=True, seed=seed))
    sample = pl.concat(frames).sort("usd_gross", descending=True)

    sample.write_parquet(OUTPUT_DIR / "wallet_sample.parquet")
    repart = (sample.group_by("stratum").len().sort("stratum")
              .select(["stratum", "len"]).rename({"len": "n_sample"}))
    summ = {
        "n_target": n,
        "seed": seed,
        "n_total_eligible": int(total),
        "n_sample_effectif": int(len(sample)),
        "alloc": alloc,
        "repartition": [dict(r) for r in repart.iter_rows(named=True)],
        "out": str(OUTPUT_DIR / "wallet_sample.parquet"),
    }
    (OUTPUT_DIR / "wsample_summary.json").write_text(json.dumps(summ, indent=2))
    print(json.dumps(summ, indent=2))
    return summ


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    main(a.n, a.seed)
