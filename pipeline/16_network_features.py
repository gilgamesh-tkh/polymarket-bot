#!/usr/bin/env python
"""Étape 7e — Features réseau X4 (contreparties) depuis quant.parquet.

quant = 1 ligne / leg avec maker & taker (casse mixte) → normaliser en minuscules.
Pour chaque wallet de l'échantillon, on construit son voisinage de trading :
  - extraire les legs où maker OU taker ∈ échantillon (semi-join, 1 scan quant ~10-15 min)
  - edges dirigés maker→taker par (maker, taker) pondérés par nb de legs & usd
  - features par wallet :
      deg_out/in (nb contreparties uniques où il est maker/taker)
      strength_out/in (usd)
      n_edges_total, n_pairs_uniques
      récurrence : part des paires rencontrées >1 fois (poids / nb paires)
      réciprocité : part des contreparties avec qui il est aussi dans l'autre sens
      auto_share : part de legs où maker == taker (self-trade, wash proxy)
Sortie : output/wallet_network.parquet
"""
import sys
import time
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import duckdb  # noqa: E402

from config import OUTPUT_DIR, pq_path  # noqa: E402

QP = pq_path("quant")
SAMPLE = str(OUTPUT_DIR / "wallet_sample.parquet")


def extract_legs(mem="6GB", threads=2):
    """1 scan quant : legs impliquant un wallet de l'échantillon."""
    con = duckdb.connect(config={"memory_limit": mem, "threads": threads})
    con.execute("SET enable_progress_bar=false")
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET temp_directory='" + str(OUTPUT_DIR.parent / ".tmp") + "'")
    t0 = time.time()
    con.execute(f"""
        COPY (
            SELECT lower(maker) AS a, lower(taker) AS b,
                   CAST(usd_amount AS DOUBLE) AS usd, 1 AS w
            FROM read_parquet('{QP}')
            WHERE lower(maker) IN (SELECT address FROM read_parquet('{SAMPLE}'))
               OR lower(taker) IN (SELECT address FROM read_parquet('{SAMPLE}'))
        ) TO '{OUTPUT_DIR / "net_legs.parquet"}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT COUNT(*) FROM '{OUTPUT_DIR/'net_legs.parquet'}'").fetchone()[0]
    print(f"net_legs: {n:,} ({time.time()-t0:.0f}s)")
    return n


def build_features():
    legs = pl.read_parquet(OUTPUT_DIR / "net_legs.parquet")
    sample = pl.read_parquet(SAMPLE, columns=["address"])
    print("legs:", len(legs))
    # edges agrégés
    ed = (legs.group_by(["a", "b"]).agg(pl.col("w").sum().alias("n_edges"),
                                        pl.col("usd").sum().alias("usd"))
          .with_columns(recurrent=(pl.col("n_edges") > 1)))
    ed.write_parquet(OUTPUT_DIR / "net_edges.parquet")
    # auto-trade
    auto = ed.filter(pl.col("a") == pl.col("b"))
    print("auto-edges (a==b):", len(auto))

    # par wallet (voisinage complet, a ou b dans échantillon) — par JOIN (évite is_in ambigu)
    def agg_wallet(col_me, col_ct):
        me = pl.col(col_me)
        ct = pl.col(col_ct)
        df = (ed.filter(me != ct)
              .join(sample.rename({"address": col_me}), on=col_me, how="inner"))
        out = (df.group_by(col_me)
               .agg(pl.col(col_ct).n_unique().alias(f"{col_me}_deg"),
                    pl.col("usd").sum().alias(f"{col_me}_str"),
                    pl.col("n_edges").sum().alias(f"{col_me}_edges"),
                    pl.col("recurrent").sum().alias(f"{col_me}_recurrent_pairs"))
               .rename({col_me: "address"}))
        return out
    out = agg_wallet("a", "b")
    out_b = agg_wallet("b", "a")
    feat = (out.join(out_b, on="address", how="full")
            .with_columns(address=pl.coalesce(pl.col("address"), pl.col("address_right")))
            .drop("address_right"))
    feat = feat.with_columns(
        [pl.col(c).fill_null(0) for c in ["a_deg", "a_str", "a_edges", "a_recurrent_pairs",
                                          "b_deg", "b_str", "b_edges", "b_recurrent_pairs"]])
    feat = feat.with_columns(
        deg_total=pl.col("a_deg") + pl.col("b_deg"),
        strength_total=pl.col("a_str") + pl.col("b_str"),
        edges_total=pl.col("a_edges") + pl.col("b_edges"),
        recurrent_total=pl.col("a_recurrent_pairs") + pl.col("b_recurrent_pairs"),
    ).with_columns(
        recurrence=pl.col("recurrent_total") / pl.col("deg_total").replace(0, None),
        recip=pl.min_horizontal([pl.col("a_deg"), pl.col("b_deg")]) / pl.col("deg_total").replace(0, None),
        avg_edge_usd=pl.col("strength_total") / pl.col("edges_total").replace(0, None),
    )
    feat.write_parquet(OUTPUT_DIR / "wallet_network.parquet")
    print("wallet_network:", len(feat), "cols:", feat.columns)
    return feat


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("all", "extract"):
        extract_legs()
    if mode in ("all", "features"):
        build_features()
