#!/usr/bin/env python
"""Détection de doublons — estimation par échantillon réservoir 1 %.

CONTEXTE RAM : le GROUP BY exact sur ~1 Md+ de lignes dépasse la RAM dispo (~2 Go libres,
memory_limit=4 Go) → OOM. Méthode retenue : échantillon réservoir aléatoire (équiréparti)
de 1 % des lignes, puis comptage EXACT des doublons dans l'échantillon.
Estimation du taux de doublons global = taux observé (non biaisé).

quant : une ligne par leg ? clé = (transaction_hash, log_index)
users : clé = (transaction_hash, log_index, address, role)
Sortie : pipeline/output/dup_<file>.json
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import OUTPUT_DIR, pq_path  # noqa: E402

import duckdb  # noqa: E402


def run(fname, key_cols, outname, sample_pct=1.0, memory_limit="8GB", threads=2):
    con = duckdb.connect(config={"memory_limit": memory_limit, "threads": threads})
    con.execute("SET enable_progress_bar=false")
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET temp_directory='" + str(OUTPUT_DIR.parent / ".tmp") + "'")
    cols = ", ".join(key_cols)
    t0 = time.time()
    df = con.execute(f"""
        WITH s AS (
            SELECT {cols}
            FROM read_parquet('{pq_path(fname)}')
            USING SAMPLE {sample_pct} PERCENT (reservoir)
        )
        SELECT COUNT(*) AS n_sample,
               COUNT(*) FILTER (WHERE c > 1) AS n_dup_rows,
               COUNT(*) FILTER (WHERE c = 2) AS n_dup2,
               COUNT(*) FILTER (WHERE c > 2) AS n_dup3plus
        FROM (SELECT {cols}, COUNT(*) AS c FROM s GROUP BY {cols}) g
    """).df().iloc[0]
    elapsed = time.time() - t0
    res = {
        "key": key_cols,
        "sample_pct": sample_pct,
        "n_sample_rows": int(df["n_sample"]),
        "n_rows_in_dup_groups": int(df["n_dup_rows"]),
        "n_dup_groups_size2": int(df["n_dup2"]),
        "n_dup_groups_size3plus": int(df["n_dup3plus"]),
        "dup_row_rate_est": float(df["n_dup_rows"]) / float(df["n_sample"]) if df["n_sample"] else None,
        "elapsed_s": round(elapsed, 1),
    }
    (OUTPUT_DIR / f"dup_{outname}.json").write_text(json.dumps(res, indent=2))
    print(outname, res)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    mem = sys.argv[2] if len(sys.argv) > 2 else "8GB"
    if which in ("all", "quant"):
        run("quant", ["transaction_hash", "log_index"], "quant", memory_limit=mem)
    if which in ("all", "users"):
        run("users", ["transaction_hash", "log_index", "address", "role"], "users",
            memory_limit=mem)
