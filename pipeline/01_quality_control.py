#!/usr/bin/env python
"""Point 2 — Contrôle qualité quant.parquet / users.parquet / markets.parquet.

Passes limitées (RAM ~2 Go, disque disponible pour le spilling) :
  - metadata : ordre temporel + stats row-group (instantané)
  - pass A (globale) : une passe par fichier — agrégats + approx distinct + bornes prix
  - pass B (temporelle) : une passe par fichier — comptes par jour (détection de trous)

Usage :
  python 01_quality_control.py --quant      # passe A+B sur quant
  python 01_quality_control.py --users      # passe A+B sur users
  python 01_quality_control.py --all
  python 01_quality_control.py --only-meta  # métadonnées seulement (rapide)
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pyarrow.parquet as pq  # noqa: E402

from config import DATA_DIR, OUTPUT_DIR, connect, pq_path  # noqa: E402

QC = {}


def meta_pass(fname):
    path = DATA_DIR / f"{fname}.parquet"
    pf = pq.ParquetFile(path)
    md = pf.metadata
    names = pf.schema.names
    i_ts = names.index("timestamp")
    i_bn = names.index("block_number")
    rng = []
    for g in range(md.num_row_groups):
        rg = md.row_group(g)
        rng.append((rg.column(i_ts).statistics.min, rg.column(i_ts).statistics.max,
                    rg.column(i_bn).statistics.min, rg.column(i_bn).statistics.max))
    ordered = all(rng[k][0] <= rng[k + 1][0] for k in range(len(rng) - 1))
    out = {
        "num_rows": md.num_rows,
        "num_row_groups": md.num_row_groups,
        "rg_time_sorted": ordered,
        "ts_min": rng[0][0],
        "ts_max": rng[-1][1],
        "biggest_rg_gaps_sec": sorted(
            ((rng[k + 1][0] - rng[k][1], k) for k in range(len(rng) - 1)), reverse=True)[:5],
    }
    return out


def pass_aggregates(fname):
    """Une seule passe : agrégats globaux + approx distinct + contrôles de bornes."""
    q = f"""
    WITH t AS (SELECT * FROM read_parquet('{pq_path(fname)}'))
    SELECT
      COUNT(*) AS n_rows,
      MIN(timestamp) AS ts_min, MAX(timestamp) AS ts_max,
      MIN(block_number) AS blk_min, MAX(block_number) AS blk_max,
      MIN(price) AS price_min, MAX(price) AS price_max,
      AVG(price) AS price_avg,
      COUNT(*) FILTER (WHERE price < 0 OR price > 1) AS n_price_oob,
      MIN(usd_amount) AS usd_min, MAX(usd_amount) AS usd_max,
      SUM(usd_amount) AS usd_sum,
      COUNT(*) FILTER (WHERE usd_amount < 0) AS n_usd_neg,
      MIN(token_amount) AS tok_min, MAX(token_amount) AS tok_max,
      SUM(token_amount) AS tok_sum,
      COUNT(*) FILTER (WHERE token_amount < 0) AS n_tok_neg,
      COUNT(*) FILTER (WHERE transaction_hash IS NULL) AS n_null_tx,
      COUNT(*) FILTER (WHERE market_id IS NULL) AS n_null_mid,
      APPROX_COUNT_DISTINCT(transaction_hash) AS approx_distinct_tx,
      APPROX_COUNT_DISTINCT(market_id) AS approx_distinct_mid
    FROM t
    """
    st = time.time()
    row = connect().execute(q).df().iloc[0]
    out = {k: (None if hasattr(v, "item") and v is None else
               (v.item() if hasattr(v, "item") else v)) for k, v in row.items()}
    if fname == "quant":
        out["approx_distinct_txlog"] = connect().execute(f"""
            SELECT APPROX_COUNT_DISTINCT(transaction_hash || ':' || CAST(log_index AS VARCHAR))
            FROM read_parquet('{pq_path(fname)}')""").fetchone()[0]
    out["_elapsed_s"] = round(time.time() - st, 1)
    return out


def pass_daily(fname):
    """Comptes par jour pour détection de trous (une passe, colonne timestamp seule)."""
    q = f"""
    WITH t AS (
      SELECT CAST(to_timestamp(timestamp) AS TIMESTAMP) AS ts
      FROM read_parquet('{pq_path(fname)}')
    )
    SELECT date_trunc('day', ts)::DATE AS day, COUNT(*) AS n
    FROM t GROUP BY 1 ORDER BY 1
    """
    st = time.time()
    df = connect().execute(q).df()
    out = {
        "days": df["day"].astype(str).tolist(),
        "counts": df["n"].astype(int).tolist(),
        "_elapsed_s": round(time.time() - st, 1),
    }
    return out


def save(fname):
    (OUTPUT_DIR / f"qc_{fname}.json").write_text(json.dumps(QC[fname], indent=2, default=str))
    print(f"[ok] {fname} -> pipeline/output/qc_{fname}.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--quant", action="store_true")
    ap.add_argument("--users", action="store_true")
    ap.add_argument("--markets", action="store_true")
    ap.add_argument("--only-meta", action="store_true")
    a = ap.parse_args()

    targets = []
    if a.all or a.quant:
        targets.append("quant")
    if a.all or a.users:
        targets.append("users")

    if a.only_meta:
        for f in ["quant", "users", "markets"]:
            QC[f] = meta_pass(f) if f != "markets" else {
                "num_rows": pq.ParquetFile(DATA_DIR / "markets.parquet").metadata.num_rows}
            save(f)
        sys.exit(0)

    for f in targets:
        print(f"=== {f} : metadata ===")
        QC[f] = {"meta": meta_pass(f)}
        if a.only_meta:
            save(f)
            continue
        print(f"=== {f} : passe agrégats (scan complet) ===")
        QC[f]["aggregates"] = pass_aggregates(f)
        print(f"    {QC[f]['aggregates']}")
        save(f)
        print(f"=== {f} : passe quotidienne (trous) ===")
        QC[f]["daily"] = pass_daily(f)
        print(f"    jours={len(QC[f]['daily']['days'])}  {QC[f]['daily']['_elapsed_s']}s")
        save(f)
