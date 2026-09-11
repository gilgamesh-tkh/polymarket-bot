#!/usr/bin/env python
"""Étape 8b — Walk-forward amélioré : features AVANCÉES pré-coupure (sans fuite).

Même coupure (2025-06-30) et même label que l'étape 8, MAIS on enrichit le jeu de
features avec toutes celles calculables sur la fenêtre timestamp < cut depuis
users_sample. Aucune feature n'utilise l'après-coupure → méthodologie intacte.

Features ajoutées vs étape 8 (basique) :
  hour_entropy, dominant_hour, weekend_frac (déjà), size_cv, roundtrip_share,
  trades_per_market, buy_sell_gap_tok1/2, arbitrage_share, cat_*_share,
  entry_timing_s, time_to_end_s, n_weeks_ratio
Sortie : output/wf_features_pre.parquet
"""
import datetime as dt
import sys
import time
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import duckdb  # noqa: E402

from config import OUTPUT_DIR, pq_path  # noqa: E402

# 2025-06-30 UTC par défaut ; peut être passé en argv (YYYY-MM-DD)
_DEF_CUT = "2025-06-30"
CUT_STR = sys.argv[1] if len(sys.argv) > 1 else _DEF_CUT
CUT_EP = int(dt.datetime.strptime(CUT_STR, "%Y-%m-%d")
             .replace(tzinfo=dt.timezone.utc).timestamp())

US = str(OUTPUT_DIR / "users_sample.parquet")


def conn(mem="5GB", threads=2):
    c = duckdb.connect(config={"memory_limit": mem, "threads": threads})
    c.execute("SET enable_progress_bar=false")
    c.execute("SET temp_directory='" + str(OUTPUT_DIR.parent / ".tmp") + "'")
    return c


def build(use_markets=True):
    c = conn()
    t0 = time.time()
    # 1) wallet-market pré-coupure (min/max ts, usd par côté) pour roundtrip, arbitrage, timing
    c.execute(f"""
        CREATE TEMP TABLE wmt AS
        SELECT address, market_id, nonusdc_side,
               MIN(timestamp) AS min_ts, MAX(timestamp) AS max_ts,
               COUNT(*) AS n, SUM(usd_amount) AS usd,
               SUM(CASE WHEN direction='BUY' THEN usd_amount ELSE 0 END) AS usd_buy,
               SUM(CASE WHEN direction='SELL' THEN usd_amount ELSE 0 END) AS usd_sell,
               AVG(price) AS avg_px
        FROM read_parquet('{US}')
        WHERE timestamp < {CUT_EP}
        GROUP BY address, market_id, nonusdc_side
    """)
    # pivot côté pour arbitrage (2 côtés présents)
    arb = c.execute("""
        WITH both_side AS (
            SELECT address, market_id FROM wmt GROUP BY address, market_id
            HAVING COUNT(DISTINCT nonusdc_side)=2
        ),
        w AS (SELECT address, COUNT(DISTINCT market_id) AS nm,
                     COUNT(DISTINCT b.market_id) AS nb
              FROM (SELECT address, market_id FROM wmt GROUP BY 1,2) x
              LEFT JOIN both_side b USING(address, market_id)
              GROUP BY address)
        SELECT address, nb::DOUBLE/NULLIF(nm,0) AS arbitrage_share FROM w
    """).df()

    # 2) wallet-market agrégé (toutes sides) pour trades_per_market, roundtrip
    wm = c.execute("""
        SELECT address,
               AVG(n) AS trades_per_market,
               AVG(CASE WHEN usd_buy>0 AND usd_sell>0 THEN 1.0 ELSE 0.0 END) AS roundtrip_share
        FROM (SELECT address, market_id, SUM(n) AS n,
                     SUM(usd_buy) AS usd_buy, SUM(usd_sell) AS usd_sell
              FROM wmt GROUP BY address, market_id) x
        GROUP BY address
    """).df()

    # 3) timing (entry/time_to_end) via markets.created_at / end_date (statiques, pas de fuite)
    timing = c.execute(f"""
        SELECT w.address,
               AVG(w.min_ts - EXTRACT(EPOCH FROM m.created_at)) AS entry_timing_s,
               AVG(EXTRACT(EPOCH FROM m.end_date) - w.max_ts) AS time_to_end_s
        FROM (SELECT address, market_id, MIN(min_ts) AS min_ts, MAX(max_ts) AS max_ts
              FROM wmt GROUP BY address, market_id) w
        JOIN read_parquet('{pq_path("markets")}') m ON w.market_id = m.id
        WHERE m.created_at IS NOT NULL AND m.end_date IS NOT NULL
        GROUP BY w.address
    """).df()

    # 4) wallet-level : heures, CV taille, prix, semaines
    c.execute(f"""
        CREATE TEMP TABLE hourly AS
        SELECT address, CAST(EXTRACT(HOUR FROM to_timestamp(timestamp)) AS INT) AS h, COUNT(*) AS c
        FROM read_parquet('{US}') WHERE timestamp < {CUT_EP}
        GROUP BY address, h
    """)
    base = c.execute(f"""
        SELECT address,
               COUNT(*) AS n_trades,
               AVG(CASE WHEN role='maker' THEN 1.0 ELSE 0.0 END) AS maker_ratio,
               SUM(usd_amount) AS usd_gross,
               SUM(usd_amount)/COUNT(*) AS avg_usd_trade,
               STDDEV(usd_amount)/NULLIF(AVG(usd_amount),0) AS size_cv,
               COUNT(DISTINCT market_id) AS n_markets,
               COUNT(DISTINCT CAST(to_timestamp(timestamp) AS DATE)) AS n_days,
               (MAX(timestamp)-MIN(timestamp))/86400.0 AS span_days,
               AVG(price) AS avg_price,
               SUM(usd_amount*ABS(price-0.5))/NULLIF(SUM(usd_amount),0) AS extremeness,
               AVG(CASE WHEN direction='BUY' THEN 1.0 ELSE 0.0 END) AS frac_buy,
               AVG(CASE WHEN nonusdc_side='token1' THEN 1.0 ELSE 0.0 END) AS frac_token1,
               AVG(CASE WHEN EXTRACT(DOW FROM to_timestamp(timestamp)) IN (0,6)
                        THEN 1.0 ELSE 0.0 END) AS weekend_frac,
               COUNT(DISTINCT CAST(EXTRACT(WEEK FROM to_timestamp(timestamp)) AS INT)
                     + 100*CAST(EXTRACT(YEAR FROM to_timestamp(timestamp)) AS INT)) AS n_weeks,
               MIN(timestamp) AS first_ts
        FROM read_parquet('{US}') WHERE timestamp < {CUT_EP}
        GROUP BY address
    """).df()

    ent = c.execute("""
        SELECT address,
               -SUM((c::DOUBLE/tot)*LN(c::DOUBLE/tot)) AS hour_entropy,
               MAX(c::DOUBLE/tot) AS dominant_hour
        FROM (SELECT address, c, SUM(c) OVER (PARTITION BY address) AS tot FROM hourly)
        GROUP BY address
    """).df()

    out = (pl.from_pandas(base)
           .join(pl.from_pandas(ent), on="address", how="left")
           .join(pl.from_pandas(arb), on="address", how="left")
           .join(pl.from_pandas(wm), on="address", how="left")
           .join(pl.from_pandas(timing), on="address", how="left"))
    # first_ts -> âge en années au moment de la coupure
    out = out.with_columns(
        age_years=(CUT_EP - pl.col("first_ts")) / (365 * 86400),
        n_weeks_ratio=pl.col("n_weeks")
        / (((CUT_EP - pl.col("first_ts")) / 604800.0) + 1))
    out.write_parquet(OUTPUT_DIR / f"wf_features_pre_{CUT_STR}.parquet")
    print(f"wf_features_pre_{CUT_STR} {len(out):,} cols={len(out.columns)} "
          f"cut={CUT_STR} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    build()
