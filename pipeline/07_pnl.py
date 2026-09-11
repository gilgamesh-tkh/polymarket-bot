#!/usr/bin/env python
"""Étape 5 — PnL réalisé + mark-to-market par (wallet, market).

Principe (fichier compact users_sample.parquet, 35,8 M lignes → RAM ok) :
  Pour chaque (address, market_id, nonusdc_side=token1|token2) :
    qty_bought/cost (BUY) et qty_sold/proceeds (SELL)
    inventory = qty_bought - qty_sold   (tokens encore détenus à la fin des données)
  Marché résolu  ⇔ markets.parquet closed=1 et outcome_prices ∈ {[1,0],[0,1]}
    payout(token1)=op[0], payout(token2)=op[1]
  PnL par marché (mark-to-market) =
      (proceeds_tok1 - cost_tok1) + (proceeds_tok2 - cost_tok2)
      + max(inventory_tok1,0)*payout1 + max(inventory_tok2,0)*payout2
    (inventaire négatif => on ne valorise pas : tokens détenus avant la fenêtre de données)
  cashflow (réalisé pur) = proceeds - cost  (sans valorisation d'inventaire)

Sorties :
  output/wallet_side.parquet     agrégats (wallet, market, side)
  output/market_resolved.parquet sous-ensemble marchés résolus
  output/wallet_pnl.parquet      PnL par (wallet, market)
  output/wallet_pnl_wallet.parquet PnL agrégé par wallet (+ win rate, ROI)
  output/pnl_summary.json
"""
import json
import sys
import time
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import duckdb  # noqa: E402

from config import OUTPUT_DIR, pq_path  # noqa: E402


def parse_op(s):
    try:
        v = json.loads(s.replace("'", '"'))
        return [float(x) for x in v]
    except Exception:
        return None


def market_resolved():
    m = pl.read_parquet(pq_path("markets")).select(
        ["id", "question", "closed", "neg_risk", "outcome_prices", "volume", "end_date"])
    op = m["outcome_prices"].map_elements(parse_op, return_dtype=pl.List(pl.Float64))
    m = m.with_columns(op.alias("op"))
    two = m.filter((pl.col("op").map_elements(len, return_dtype=pl.Int64) == 2))
    # résolu : valeurs exactes [1,0] ou [0,1]
    def reso(o):
        if o is None or len(o) != 2:
            return None
        if o[0] == 1.0 and o[1] == 0.0:
            return "token1"
        if o[0] == 0.0 and o[1] == 1.0:
            return "token2"
        return None
    r = (two.with_columns(
        pl.col("op").map_elements(reso, return_dtype=pl.String).alias("winner"))
         .filter(pl.col("winner").is_not_null())
         .with_columns(payout1=pl.when(pl.col("winner") == "token1").then(1.0).otherwise(0.0),
                       payout2=pl.when(pl.col("winner") == "token2").then(1.0).otherwise(0.0)))
    r.write_parquet(OUTPUT_DIR / "market_resolved.parquet")
    print("marchés résolus binaires:", len(r))
    return r


def wallet_side(mem="4GB", threads=2):
    con = duckdb.connect(config={"memory_limit": mem, "threads": threads})
    con.execute("SET enable_progress_bar=false")
    con.execute("SET temp_directory='" + str(OUTPUT_DIR.parent / ".tmp") + "'")
    t0 = time.time()
    con.execute(f"""
        COPY (
            SELECT u.address, u.market_id, u.nonusdc_side,
                   COUNT(*) AS n,
                   SUM(CASE WHEN u.direction='BUY'  THEN u.usd_amount END) AS cost,
                   SUM(CASE WHEN u.direction='SELL' THEN u.usd_amount END) AS proceeds,
                   SUM(CASE WHEN u.direction='BUY'  THEN u.token_amount END) AS qty_bought,
                   SUM(CASE WHEN u.direction='SELL' THEN u.token_amount END) AS qty_sold,
                   AVG(u.price) AS avg_price
            FROM read_parquet('{OUTPUT_DIR/'users_sample.parquet'}') u
            GROUP BY u.address, u.market_id, u.nonusdc_side
        ) TO '{OUTPUT_DIR/'wallet_side.parquet'}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """)
    n = con.execute(f"SELECT COUNT(*) FROM '{OUTPUT_DIR/'wallet_side.parquet'}'").fetchone()[0]
    res = {"n_wallet_side": int(n), "elapsed_s": round(time.time() - t0, 1)}
    print(res)
    (OUTPUT_DIR / "wside_summary.json").write_text(json.dumps(res, indent=2))


def pnl():
    ws = pl.read_parquet(OUTPUT_DIR / "wallet_side.parquet")
    mr = pl.read_parquet(OUTPUT_DIR / "market_resolved.parquet").select(
        ["id", "winner", "payout1", "payout2"]).rename({"id": "market_id"})

    # pivot par côté
    p1 = ws.filter(pl.col("nonusdc_side") == "token1").drop("nonusdc_side").rename(
        {"n": "n1", "cost": "cost1", "proceeds": "proceeds1",
         "qty_bought": "qb1", "qty_sold": "qs1", "avg_price": "p1"})
    p2 = ws.filter(pl.col("nonusdc_side") == "token2").drop("nonusdc_side").rename(
        {"n": "n2", "cost": "cost2", "proceeds": "proceeds2",
         "qty_bought": "qb2", "qty_sold": "qs2", "avg_price": "p2"})
    wm = p1.join(p2, on=["address", "market_id"], how="full").with_columns(
        [pl.col(c).fill_null(0) for c in
         ["cost1", "proceeds1", "qb1", "qs1", "cost2", "proceeds2", "qb2", "qs2"]])
    wm = wm.join(mr, on="market_id", how="left").with_columns(
        inventory1=pl.col("qb1") - pl.col("qs1"),
        inventory2=pl.col("qb2") - pl.col("qs2"),
    ).with_columns(
        resolved=pl.col("winner").is_not_null(),
        cashflow=(pl.col("proceeds1") - pl.col("cost1")) + (pl.col("proceeds2") - pl.col("cost2")),
    ).with_columns(
        inv_value1=pl.max_horizontal([pl.col("inventory1"), pl.lit(0)]) * pl.col("payout1"),
        inv_value2=pl.max_horizontal([pl.col("inventory2"), pl.lit(0)]) * pl.col("payout2"),
    ).with_columns(
        pnl_m2m=pl.col("cashflow")
                + pl.when(pl.col("resolved")).then(pl.col("inv_value1") + pl.col("inv_value2"))
                .otherwise(pl.lit(0.0)),
        pnl_realized=pl.col("cashflow"),
    )
    keep = ["address", "market_id", "n1", "n2", "cost1", "proceeds1", "cost2", "proceeds2",
            "qb1", "qs1", "qb2", "qs2", "inventory1", "inventory2", "resolved", "winner",
            "cashflow", "inv_value1", "inv_value2", "pnl_m2m", "pnl_realized"]
    wm.select(keep).write_parquet(OUTPUT_DIR / "wallet_pnl.parquet")

    # agrégation wallet
    # win rate sur marchés RÉSOLUS uniquement : gagné = pnl_m2m>0 parmi resolved
    resolved = wm.filter(pl.col("resolved"))
    wr = (resolved.group_by("address")
          .agg((pl.col("pnl_m2m") > 0).sum().alias("n_resolved_won"),
               (pl.col("pnl_m2m") < 0).sum().alias("n_resolved_lost"),
               pl.col("pnl_m2m").count().alias("n_markets_resolved"),
               )
          .with_columns(win_rate_m2m=pl.col("n_resolved_won") / pl.col("n_markets_resolved")))
    w = (wm.group_by("address")
         .agg(
             pl.col("market_id").count().alias("n_markets_traded"),
             pl.col("pnl_realized").sum().alias("pnl_realized"),
             pl.col("pnl_m2m").sum().alias("pnl_m2m"),
             pl.col("cashflow").sum().alias("cashflow"),
             pl.col("cost1").sum().alias("cost1"), pl.col("cost2").sum().alias("cost2"),
             pl.col("proceeds1").sum().alias("proceeds1"),
             pl.col("proceeds2").sum().alias("proceeds2"),
             (pl.col("pnl_m2m") > 0).sum().alias("n_markets_pnl_pos_m2m"),
             (pl.col("pnl_m2m") < 0).sum().alias("n_markets_pnl_neg_m2m"),
         )
         .with_columns(
             total_cost=pl.col("cost1") + pl.col("cost2"),
             total_proceeds=pl.col("proceeds1") + pl.col("proceeds2"),
         )
         .with_columns(
             roi_m2m=pl.col("pnl_m2m") / pl.col("total_cost").replace(0, None),
             roi_realized=pl.col("pnl_realized") / pl.col("total_cost").replace(0, None),
         )
         .join(wr, on="address", how="left"))
    w.write_parquet(OUTPUT_DIR / "wallet_pnl_wallet.parquet")
    print("wallets:", len(w))
    return w


def summary(w):
    s = {
        "n_wallets": int(len(w)),
        "n_wallets_pos_pnl_m2m": int((w["pnl_m2m"] > 0).sum()),
        "pct_pos_m2m": round(100 * (w["pnl_m2m"] > 0).mean(), 2),
        "n_wallets_pos_realized": int((w["pnl_realized"] > 0).sum()),
        "pct_pos_realized": round(100 * (w["pnl_realized"] > 0).mean(), 2),
        "median_pnl_m2m": float(w["pnl_m2m"].median()),
        "median_roi_m2m": float(w["roi_m2m"].median()),
        "median_win_rate": float(w["win_rate_m2m"].median()),
        "pct_roi_gt20": round(100 * (w["roi_m2m"] > 0.20).mean(), 2),
        "pct_winrate_gt65": round(100 * (w["win_rate_m2m"] > 0.65).mean(), 2),
    }
    (OUTPUT_DIR / "pnl_summary.json").write_text(json.dumps(s, indent=2))
    print(json.dumps(s, indent=2))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("all", "markets"):
        market_resolved()
    if mode in ("all", "side"):
        wallet_side()
    if mode in ("all", "pnl"):
        w = pnl()
        summary(w)
