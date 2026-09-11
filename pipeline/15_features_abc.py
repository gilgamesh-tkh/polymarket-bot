#!/usr/bin/env python
"""Étape 7d — Features A+B+C pour renforcer le classifieur H1.

A. Timing & expérience (users_sample) :
   first_seen_ts, entry_timing (1er trade - created_at marché), time_to_end
   (end_date - dernier trade), dominant_hour_share, n_weeks_ratio, price_range
B. Style d'exécution (wallet_market) :
   trades_per_market, roundtrip_share, side_imbalance
C. Liquidité / sophistication (joins markets) :
   mkt_impact (taille trade / volume marché), buy_sell_gap par côté,
   cat_sports/politics/crypto/other (part volume), arbitrage_share (2 côtés)

Sortie : output/wallet_features_abc.parquet
"""
import sys
import time
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import duckdb  # noqa: E402

from config import OUTPUT_DIR, pq_path  # noqa: E402

US = str(OUTPUT_DIR / "users_sample.parquet")
WM = str(OUTPUT_DIR / "wallet_market.parquet")
WS = str(OUTPUT_DIR / "wallet_side.parquet")


def conn(mem="5GB", threads=2):
    c = duckdb.connect(config={"memory_limit": mem, "threads": threads})
    c.execute("SET enable_progress_bar=false")
    c.execute("SET temp_directory='" + str(OUTPUT_DIR.parent / ".tmp") + "'")
    return c


def market_cats():
    """Catégorise chaque marché par mots-clés + volume. (1,8 M lignes, léger)."""
    m = pl.read_parquet(pq_path("markets"), columns=["id", "question", "event_title", "volume"])
    q = (m["question"].fill_null("") + " " + m["event_title"].fill_null("")).str.to_lowercase()
    def cat(s):
        if any(k in s for k in [" vs ", "over/under", "o/u ", "nba", "nfl", "mlb", "nhl",
                                "ufc", "tennis", "soccer", "football", "basketball", "hockey",
                                "match", "corner", "goal", "race", "fight", "game "]):
            return "sports"
        if any(k in s for k in ["bitcoin", "btc", "ethereum", "eth ", "solana", "sol ",
                                "crypto", "coin", "token", "price of"]):
            return "crypto"
        if any(k in s for k in ["election", "president", "senate", "house", "democrat",
                                "republican", "trump", "biden", "prime minister", "minister",
                                "vote", "ballot", "parliament", "leader"]):
            return "politics"
        return "other"
    out = m.select(["id", "volume"]).with_columns(
        pl.col("volume").log1p().alias("logvol"),
        pl.Series("category", q.map_elements(cat, return_dtype=pl.Utf8)))
    out.write_parquet(OUTPUT_DIR / "markets_cat.parquet")
    print("markets categorisés:", len(out))
    return out


def features_a():
    """Timing & expérience — depuis users_sample."""
    c = conn()
    t0 = time.time()
    # wallet-market time stats (min/max ts) en 1 passe
    c.execute(f"""
        CREATE TEMP TABLE wmt AS
        SELECT address, market_id, MIN(timestamp) AS min_ts, MAX(timestamp) AS max_ts
        FROM read_parquet('{US}')
        GROUP BY address, market_id
    """)
    # join markets created_at/end_date
    c.execute(f"""
        CREATE TEMP TABLE wmtj AS
        SELECT w.address,
               AVG(w.min_ts - EXTRACT(EPOCH FROM m.created_at)) AS entry_timing_s,
               AVG(EXTRACT(EPOCH FROM m.end_date) - w.max_ts)   AS time_to_end_s
        FROM wmt w
        JOIN read_parquet('{pq_path("markets")}') m ON w.market_id = m.id
        WHERE m.created_at IS NOT NULL AND m.end_date IS NOT NULL
        GROUP BY w.address
    """)
    # address-level : heures dominantes, semaines, range de prix
    c.execute(f"""
        CREATE TEMP TABLE hourly AS
        SELECT address, CAST(EXTRACT(HOUR FROM to_timestamp(timestamp)) AS INT) AS h,
               COUNT(*) AS c
        FROM read_parquet('{US}')
        GROUP BY address, h
    """)
    c.execute("""
        CREATE TEMP TABLE addr AS
        SELECT address,
               MIN(timestamp) AS first_ts,
               COUNT(DISTINCT CAST(EXTRACT(WEEK FROM to_timestamp(timestamp)) AS INT)
                     + 100*CAST(EXTRACT(YEAR FROM to_timestamp(timestamp)) AS INT)) AS n_weeks,
               MAX(price) - MIN(price) AS price_range,
               COUNT(*) AS n
        FROM read_parquet('{0}')
        GROUP BY address
    """.replace("{0}", US))
    a = c.execute("""
        SELECT ad.address,
               ad.first_ts,
               ad.n_weeks::DOUBLE / NULLIF((MAX(ad.first_ts) OVER () - ad.first_ts)/604800.0 + 1, 0)
                   AS n_weeks_ratio,
               ad.price_range,
               j.entry_timing_s,
               j.time_to_end_s,
               h.max_share AS dominant_hour_share
        FROM addr ad
        LEFT JOIN wmtj j ON ad.address = j.address
        LEFT JOIN (SELECT address, MAX(c::DOUBLE/tot) AS max_share
                   FROM (SELECT address, c, SUM(c) OVER (PARTITION BY address) AS tot FROM hourly)
                   GROUP BY address) h ON ad.address = h.address
    """).df()
    out = pl.from_pandas(a)
    print(f"A done {len(out):,} ({time.time()-t0:.0f}s)")
    return out


def features_bc(mc):
    """Style d'exécution (wallet_market) + liquidité/catégories + arbitrage (wallet_side)."""
    c = conn()
    t0 = time.time()
    # wallet_market join markets_cat
    mc_p = str(OUTPUT_DIR / "markets_cat.parquet")
    c.execute(f"""
        CREATE TEMP TABLE wmj AS
        SELECT w.address,
               w.market_id,
               w.n, w.n_buy, w.n_sell, w.usd_buy, w.usd_sell, w.usd_gross,
               mc.logvol, mc.category
        FROM read_parquet('{WM}') w
        JOIN read_parquet('{mc_p}') mc ON w.market_id = mc.id
    """)
    b = c.execute("""
        SELECT address,
               AVG(n) AS trades_per_market,
               AVG(CASE WHEN n_buy > 0 AND n_sell > 0 THEN 1.0 ELSE 0.0 END) AS roundtrip_share,
               AVG(ABS(usd_buy - usd_sell) / NULLIF(usd_gross,0)) AS side_imbalance,
               AVG(usd_gross / NULLIF(EXP(logvol)-1 + 1e-6, 0)) AS mkt_impact_avg,
               MEDIAN(usd_gross / NULLIF(EXP(logvol)-1 + 1e-6, 0)) AS mkt_impact_med
        FROM wmj
        GROUP BY address
    """).df()
    # catégories : part de volume (usd_gross) par catégorie
    cat = c.execute("""
        SELECT address, category, SUM(usd_gross) AS v
        FROM wmj GROUP BY address, category
    """).df()
    catp = (pl.from_pandas(cat).pivot(values="v", index="address", columns="category")
            .fill_null(0.0))
    for col in ["sports", "crypto", "politics", "other"]:
        if col not in catp.columns:
            catp = catp.with_columns(pl.lit(0.0).alias(col))
    tot = sum(catp[c] for c in ["sports", "crypto", "politics", "other"])
    catp = catp.with_columns([(catp[c] / tot.replace(0, None)).alias(f"cat_{c}_share")
                              for c in ["sports", "crypto", "politics", "other"]])

    # arbitrage : marchés où le wallet a les 2 côtés (qty_bought>0 token1 & token2)
    arb = c.execute(f"""
        WITH both_side AS (
            SELECT s.address, s.market_id
            FROM read_parquet('{WS}') s
            GROUP BY s.address, s.market_id
            HAVING COUNT(DISTINCT nonusdc_side) = 2
        ),
        per_wallet AS (
            SELECT s.address, COUNT(DISTINCT s.market_id) AS n_mkts,
                   COUNT(DISTINCT b.market_id) AS n_both
            FROM read_parquet('{WS}') s
            LEFT JOIN both_side b ON s.address = b.address AND s.market_id = b.market_id
            GROUP BY s.address
        )
        SELECT address, n_both::DOUBLE / NULLIF(n_mkts,0) AS arbitrage_share
        FROM per_wallet
    """).df()

    out = (pl.from_pandas(b)
           .join(catp.select(["address"] + [f"cat_{x}_share" for x in
                                            ["sports", "crypto", "politics", "other"]]),
                 on="address", how="left")
           .join(pl.from_pandas(arb), on="address", how="left"))
    print(f"B+C done {len(out):,} ({time.time()-t0:.0f}s)")
    return out


def buy_sell_gap():
    """Écart prix d'achat vs prix de vente, par côté (token1/token2)."""
    c = conn()
    t0 = time.time()
    g = c.execute(f"""
        SELECT address, nonusdc_side, direction,
               AVG(price) AS avg_px, SUM(usd_amount) AS v
        FROM read_parquet('{US}')
        GROUP BY address, nonusdc_side, direction
    """).df()
    gp = (pl.from_pandas(g).pivot(values="avg_px", index="address",
                                  columns=["nonusdc_side", "direction"]))
    # colonnes plat
    cols = gp.columns
    g1 = (pl.from_pandas(g).filter(pl.col("nonusdc_side") == "token1")
          .pivot(values="avg_px", index="address", columns="direction").rename(
              {"BUY": "buy_px_tok1", "SELL": "sell_px_tok1"}))
    g2 = (pl.from_pandas(g).filter(pl.col("nonusdc_side") == "token2")
          .pivot(values="avg_px", index="address", columns="direction").rename(
              {"BUY": "buy_px_tok2", "SELL": "sell_px_tok2"}))
    out = (g1.join(g2, on="address", how="full")
           .drop("address_right")
           .with_columns([
               (pl.col("sell_px_tok1").fill_null(pl.col("buy_px_tok1"))
                - pl.col("buy_px_tok1").fill_null(pl.col("sell_px_tok1")))
               .alias("buy_sell_gap_tok1"),
               (pl.col("sell_px_tok2").fill_null(pl.col("buy_px_tok2"))
                - pl.col("buy_px_tok2").fill_null(pl.col("sell_px_tok2")))
               .alias("buy_sell_gap_tok2")]))
    out = out.select(["address", "buy_px_tok1", "sell_px_tok1", "buy_sell_gap_tok1",
                      "buy_px_tok2", "sell_px_tok2", "buy_sell_gap_tok2"])
    print(f"gap done {len(out):,} ({time.time()-t0:.0f}s)")
    return out


def main():
    mc = market_cats()
    a = features_a()
    bc = features_bc(mc)
    gap = buy_sell_gap()
    df = a.join(bc, on="address", how="full")
    for c in [c for c in df.columns if c.endswith("_right")]:
        df = df.drop(c)
    df = df.join(gap.drop("address_right"), on="address", how="full") if "address_right" in gap.columns else df.join(gap, on="address", how="full")
    df = df.unique(subset=["address"])
    df.write_parquet(OUTPUT_DIR / "wallet_features_abc.parquet")
    print("cols:", df.columns)
    print("[ok] output/wallet_features_abc.parquet  rows:", len(df))


if __name__ == "__main__":
    main()
