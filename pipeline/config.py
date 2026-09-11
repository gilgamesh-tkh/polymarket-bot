"""Configuration partagée du pipeline Smart Money (dataset SII-WANGZJ/Polymarket_data)."""
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[1]
DATA_DIR = REPO / "Polymarket_data" / "data"
OUTPUT_DIR = REPO / "pipeline" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FILES = {
    "markets": DATA_DIR / "markets.parquet",
    "quant": DATA_DIR / "quant.parquet",
    "users": DATA_DIR / "users.parquet",
}

# RAM dispo faible (~2 Go libres) : on borne DuckDB et on lui donne un temp dir dispo.
MEMORY_LIMIT = "4GB"
THREADS = 4


def connect():
    con = duckdb.connect(config={"memory_limit": MEMORY_LIMIT, "threads": THREADS})
    con.execute("SET enable_progress_bar=false")
    con.execute("SET temp_directory='" + str(REPO / "pipeline" / ".tmp") + "'")
    return con


def pq_path(name: str) -> str:
    return str(FILES[name])
