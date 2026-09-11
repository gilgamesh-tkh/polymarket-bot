#!/usr/bin/env python
"""Étape 3 — Table wallet-level (X1–X3) sous contrainte RAM.

Stratégie : aucune table intermédiaire ne doit tenir en RAM. On fait des GROUP BY
DuckDB qui spillent sur disque (temp_directory, 300 Go libres) et on écrit chaque
sous-produit en parquet. Aucun .collect() massif.

Sous-commandes :
  --primitives      3a. GROUP BY address sur users.parquet (1 passe) -> wallet_primitives.parquet
  --include        3b. Filtres d'inclusion + stats population (lecture parquet primitives)
  --wallet-market  3c. GROUP BY (address, market_id) restreint à l'échantillon -> wallet_market.parquet
                    (nécessite les parquet des étapes précédentes)
  --extract-sample 3c'. Matérialise les lignes users de l'échantillon dans users_sample.parquet
                    (1 scan users) puis toutes les passes fines se font sur ce petit fichier.

Usage:
  python 04_wallet_features.py --primitives --memory 8GB --threads 2
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import duckdb  # noqa: E402

from config import OUTPUT_DIR, pq_path  # noqa: E402

PRIM = OUTPUT_DIR / "wallet_primitives.parquet"


def conn(mem, threads):
    c = duckdb.connect(config={"memory_limit": mem, "threads": threads})
    c.execute("SET enable_progress_bar=false")
    c.execute("SET preserve_insertion_order=false")
    c.execute("SET temp_directory='" + str(OUTPUT_DIR.parent / ".tmp") + "'")
    return c


def primitives(mem, threads):
    t0 = time.time()
    con = conn(mem, threads)
    q = f"""
    WITH t AS (
        SELECT address, timestamp, role, direction, usd_amount, token_amount, price,
               market_id, event_id
        FROM read_parquet('{pq_path("users")}')
        WHERE price BETWEEN 0 AND 1
    )
    SELECT
        address,
        COUNT(*)                                              AS n_trades,
        COUNT(*) FILTER (WHERE direction = 'BUY')             AS n_buy,
        COUNT(*) FILTER (WHERE direction = 'SELL')            AS n_sell,
        COUNT(*) FILTER (WHERE role = 'maker')                AS n_maker,
        COUNT(*) FILTER (WHERE role = 'taker')                AS n_taker,
        SUM(usd_amount) FILTER (WHERE direction = 'BUY')      AS usd_buy,
        SUM(usd_amount) FILTER (WHERE direction = 'SELL')     AS usd_sell,
        SUM(usd_amount)                                       AS usd_gross,
        SUM(token_amount) FILTER (WHERE direction = 'BUY')    AS tok_buy,
        SUM(token_amount) FILTER (WHERE direction = 'SELL')   AS tok_sell,
        APPROX_COUNT_DISTINCT(market_id)                      AS n_markets_apx,
        APPROX_COUNT_DISTINCT(event_id)                       AS n_events_apx,
        APPROX_COUNT_DISTINCT(CAST(to_timestamp(timestamp) AS DATE)) AS n_days_active_apx,
        MIN(timestamp)                                        AS ts_first,
        MAX(timestamp)                                        AS ts_last,
        AVG(price)                                            AS avg_price,
        SUM(usd_amount * price) / NULLIF(SUM(usd_amount), 0)  AS vwap
    FROM t
    GROUP BY address
    """
    con.execute(f"COPY ({q}) TO '{PRIM}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    n = con.execute(f"SELECT COUNT(*) FROM '{PRIM}'").fetchone()[0]
    el = time.time() - t0
    res = {"n_wallets": n, "elapsed_s": round(el, 1), "out": str(PRIM)}
    (OUTPUT_DIR / "wprim_summary.json").write_text(json.dumps(res, indent=2))
    print(res)
    return res


def include():
    """Lit wallet_primitives, applique les critères d'inclusion, sauve la population filtrée."""
    con = conn("2GB", 2)
    df = con.execute(f"""
        SELECT *,
               (ts_last - ts_first) / 86400.0 AS span_days
        FROM '{PRIM}'
    """).df()
    tot = len(df)
    crit = df[
        (df["n_trades"] > 100)
        & (df["usd_gross"] > 1000)
        & (df["n_markets_apx"] > 3)
        & ((df["ts_last"] - df["ts_first"]) / 86400.0 > 30)
    ].copy()
    crit.to_parquet(OUTPUT_DIR / "wallet_eligible.parquet", index=False)
    summ = {
        "population_wallets": int(tot),
        "eligible_wallets": int(len(crit)),
        "pct_eligible": round(100 * len(crit) / tot, 3) if tot else 0,
        "usd_gross_total": float(crit["usd_gross"].sum()) if len(crit) else 0,
    }
    (OUTPUT_DIR / "wincl_summary.json").write_text(json.dumps(summ, indent=2))
    print(summ)
    return summ


def extract_sample(mem, threads, sample=None):
    """Matérialise les lignes users appartenant à l'échantillon (une seule passe)."""
    con = conn(mem, threads)
    if sample is None:
        sample = str(OUTPUT_DIR / "wallet_sample.parquet")
    t0 = time.time()
    con.execute(f"""
        COPY (
            SELECT u.timestamp, u.block_number, u.transaction_hash, u.log_index,
                   u.address, u.role, u.direction, u.usd_amount, u.token_amount,
                   u.price, u.market_id, u.condition_id, u.event_id, u.nonusdc_side
            FROM read_parquet('{pq_path("users")}') u
            JOIN read_parquet('{sample}') s ON s.address = u.address
            WHERE u.price BETWEEN 0 AND 1
        ) TO '{OUTPUT_DIR / "users_sample.parquet"}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(f"SELECT COUNT(*) FROM '{OUTPUT_DIR/'users_sample.parquet'}'").fetchone()[0]
    res = {"n_rows_sample": n, "elapsed_s": round(time.time() - t0, 1)}
    (OUTPUT_DIR / "usample_summary.json").write_text(json.dumps(res, indent=2))
    print(res)
    return res


def wallet_market(mem, threads, sample=None):
    """3c : agrégats (address, market_id) — lit users_sample.parquet s'il existe, sinon rescan."""
    con = conn(mem, threads)
    src = OUTPUT_DIR / "users_sample.parquet"
    if src.exists():
        users_src = str(src)
    else:
        users_src = pq_path("users")
    if sample is None:
        p = OUTPUT_DIR / "wallet_sample.parquet"
        if not p.exists():
            p = OUTPUT_DIR / "wallet_eligible.parquet"
        assert p.exists(), "lance d'abord --include"
        sample = str(p)
    t0 = time.time()
    q = f"""
    COPY (
        SELECT u.address, u.market_id,
               COUNT(*)                       AS n,
               COUNT(*) FILTER (WHERE u.direction='BUY')  AS n_buy,
               COUNT(*) FILTER (WHERE u.direction='SELL') AS n_sell,
               SUM(CASE WHEN u.direction='BUY'  THEN u.usd_amount END) AS usd_buy,
               SUM(CASE WHEN u.direction='SELL' THEN u.usd_amount END) AS usd_sell,
               SUM(u.usd_amount)               AS usd_gross,
               SUM(CASE WHEN u.direction='BUY'  THEN u.token_amount END) AS tok_buy,
               SUM(CASE WHEN u.direction='SELL' THEN u.token_amount END) AS tok_sell,
               AVG(u.price)                    AS avg_price
        FROM read_parquet('{users_src}') u
        JOIN read_parquet('{sample}') s ON s.address = u.address
        GROUP BY u.address, u.market_id
    ) TO '{OUTPUT_DIR / "wallet_market.parquet"}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """
    con.execute(q)
    n = con.execute(f"SELECT COUNT(*) FROM '{OUTPUT_DIR/'wallet_market.parquet'}'").fetchone()[0]
    res = {"n_wallet_market_rows": n, "elapsed_s": round(time.time() - t0, 1)}
    (OUTPUT_DIR / "wmark_summary.json").write_text(json.dumps(res, indent=2))
    print(res)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--primitives", action="store_true")
    ap.add_argument("--include", action="store_true")
    ap.add_argument("--wallet-market", action="store_true")
    ap.add_argument("--extract-sample", action="store_true")
    ap.add_argument("--memory", default="6GB")
    ap.add_argument("--threads", type=int, default=2)
    a = ap.parse_args()
    if a.primitives:
        primitives(a.memory, a.threads)
    if a.include:
        include()
    if a.extract_sample:
        extract_sample(a.memory, a.threads)
    if a.wallet_market:
        wallet_market(a.memory, a.threads)
