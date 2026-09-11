#!/usr/bin/env python
"""Étape 7b — Features enrichies pour le classifieur H1 (pas de fuite).

Ajoute aux 12 features de l'étape 7 des descripteurs comportementaux fins :
  Profil temporel (users_sample) :
    weekend_frac, hour_entropy (24h), size_cv (variabilité taille de trade),
    extremeness (moyenne pondérée |price-0.5|), frac_token1 (préférence de côté)
  Sélection de marchés (wallet_market ⋈ markets) :
    mkt_vol_med (log volume médian des marchés tradés), mkt_negrisk_share,
    mkt_horizon_days_med (durée de vie médiane des marchés tradés)
Sortie : output/wallet_features_adv.parquet
"""
import sys
import time
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import duckdb  # noqa: E402

from config import OUTPUT_DIR, pq_path  # noqa: E402


def temporal(mem="5GB", threads=2):
    con = duckdb.connect(config={"memory_limit": mem, "threads": threads})
    con.execute("SET enable_progress_bar=false")
    con.execute("SET temp_directory='" + str(OUTPUT_DIR.parent / ".tmp") + "'")
    t0 = time.time()
    # hour = heure UTC
    con.execute(f"""
        CREATE TEMP TABLE agg1 AS
        SELECT address,
               COUNT(*) AS n,
               AVG(usd_amount) AS avg_usd,
               STDDEV(usd_amount) AS sd_usd,
               AVG(CASE WHEN direction='BUY' THEN 1.0 ELSE 0.0 END) AS frac_buy,
               AVG(CASE WHEN role='maker' THEN 1.0 ELSE 0.0 END) AS frac_maker,
               SUM(usd_amount*ABS(price-0.5))/NULLIF(SUM(usd_amount),0) AS extremeness,
               AVG(CASE WHEN nonusdc_side='token1' THEN 1.0 ELSE 0.0 END) AS frac_token1,
               AVG(CASE WHEN EXTRACT(DOW FROM to_timestamp(timestamp)) IN (0,6)
                        THEN 1.0 ELSE 0.0 END) AS weekend_frac
        FROM read_parquet('{OUTPUT_DIR/'users_sample.parquet'}')
        GROUP BY address
    """)
    # entropie horaire : part par heure -> -sum(p ln p)
    con.execute(f"""
        CREATE TEMP TABLE hourly AS
        SELECT address, CAST(EXTRACT(HOUR FROM to_timestamp(timestamp)) AS INT) AS h,
               COUNT(*) AS c
        FROM read_parquet('{OUTPUT_DIR/'users_sample.parquet'}')
        GROUP BY address, h
    """)
    ent = con.execute("""
        SELECT address,
               -SUM((c::DOUBLE / tot) * LN(c::DOUBLE / tot)) AS hour_entropy
        FROM (SELECT address, h, c, SUM(c) OVER (PARTITION BY address) AS tot FROM hourly)
        GROUP BY address
    """).df()
    a1 = con.execute("""
        SELECT address, n, avg_usd, sd_usd,
               CASE WHEN avg_usd>0 THEN sd_usd/avg_usd ELSE NULL END AS size_cv,
               frac_buy, frac_maker, extremeness, frac_token1, weekend_frac
        FROM agg1
    """).df()
    out = pl.from_pandas(a1).join(pl.from_pandas(ent), on="address", how="left")
    print(f"temporal done {len(out):,} ({time.time()-t0:.0f}s)")
    return out


def markets(mem="5GB", threads=2):
    con = duckdb.connect(config={"memory_limit": mem, "threads": threads})
    con.execute("SET enable_progress_bar=false")
    con.execute("SET temp_directory='" + str(OUTPUT_DIR.parent / ".tmp") + "'")
    t0 = time.time()
    con.execute(f"""
        CREATE TEMP TABLE mkt AS
        SELECT w.address,
               MEDIAN(LOG(1+m.volume)) AS mkt_vol_med,
               AVG(CASE WHEN m.neg_risk=1 THEN 1.0 ELSE 0.0 END) AS mkt_negrisk_share,
               MEDIAN(EXTRACT(EPOCH FROM (m.end_date - m.created_at))/86400.0)
                   AS mkt_horizon_days_med
        FROM read_parquet('{OUTPUT_DIR/'wallet_market.parquet'}') w
        JOIN read_parquet('{pq_path("markets")}') m
          ON w.market_id = m.id
        GROUP BY w.address
    """)
    out = pl.from_pandas(con.execute("SELECT * FROM mkt").df())
    print(f"markets done {len(out):,} ({time.time()-t0:.0f}s)")
    return out


def main():
    t = temporal()
    m = markets()
    df = t.join(m, on="address", how="full").drop("address_right")
    df.write_parquet(OUTPUT_DIR / "wallet_features_adv.parquet")
    print("cols:", df.columns)
    print("[ok] output/wallet_features_adv.parquet")


if __name__ == "__main__":
    main()
