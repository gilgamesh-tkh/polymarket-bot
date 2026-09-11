#!/usr/bin/env python
"""Étape 9-H3 — Anomalies de volume sur marchés longshots (faible liquidité).

Périmètre : marchés résolus binaires créés en 2025, volume 1k-50k$ (h3_markets.parquet).
Une passe sur quant.parquet : agrégats horaires (volume usd, prix moyen) par marché.

Sortie : output/h3_hourly.parquet
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import duckdb  # noqa: E402
import polars as pl

from config import OUTPUT_DIR, pq_path  # noqa: E402

MARKETS = str(OUTPUT_DIR / "h3_markets.parquet")


def aggregate(mem="6GB", threads=2):
    con = duckdb.connect(config={"memory_limit": mem, "threads": threads})
    con.execute("SET enable_progress_bar=false")
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET temp_directory='" + str(OUTPUT_DIR.parent / ".tmp") + "'")
    t0 = time.time()
    con.execute(f"""
        COPY (
            SELECT q.market_id,
                   CAST(to_timestamp(q.timestamp) AS TIMESTAMP) - INTERVAL (EXTRACT(MINUTE FROM to_timestamp(q.timestamp))::INT) MINUTE
                     - INTERVAL (EXTRACT(SECOND FROM to_timestamp(q.timestamp))::INT) SECOND AS hour_ts,
                   SUM(q.usd_amount) AS vol_usd,
                   COUNT(*) AS n_trades,
                   AVG(q.price) AS avg_price,
                   MIN(q.price) AS min_price,
                   MAX(q.price) AS max_price
            FROM read_parquet('{pq_path("quant")}') q
            JOIN read_parquet('{MARKETS}') m ON q.market_id = m.market_id
            WHERE q.price BETWEEN 0 AND 1
            GROUP BY q.market_id, hour_ts
        ) TO '{OUTPUT_DIR/'h3_hourly.parquet'}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT COUNT(*) FROM '{OUTPUT_DIR/'h3_hourly.parquet'}'").fetchone()[0]
    print(f"h3_hourly rows: {n:,} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    aggregate()
