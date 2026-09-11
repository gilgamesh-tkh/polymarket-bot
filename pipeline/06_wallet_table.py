#!/usr/bin/env python
"""Étape 3d — Table wallet finale X1–X3 depuis wallet_market.parquet (fichier compact).

Pour chaque wallet de l'échantillon, agrège ses paires address×market :
  X1 performance : net_cashflow (usd_sell - usd_buy), roi_cashflow, win_market_proxy,
                   perte/gain brut, nb marchés à PnL+ / PnL-
  X3 diversification : n_markets, HHI(volume), entropie de Shannon(volume)
Colonnes des primitives (X1/X2) déjà disponibles dans wallet_eligible.parquet :
n_trades, usd_buy/sell/gross, n_maker/taker, n_days, avg_price, vwap...

Sortie : pipeline/output/wallet_table.parquet + wallet_table.csv.gz (léger, hors git)
"""
import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import OUTPUT_DIR  # noqa: E402

OUT_TABLE = OUTPUT_DIR / "wallet_table.parquet"


def main():
    wm = pl.read_parquet(OUTPUT_DIR / "wallet_market.parquet")
    prim = pl.read_parquet(OUTPUT_DIR / "wallet_eligible.parquet")

    # ---- features par marché pour calculs (reste en mémoire: 5,4 M lignes x qq cols) ----
    m = wm.with_columns(
        net_cashflow=pl.col("usd_sell").fill_null(0) - pl.col("usd_buy").fill_null(0),
        vol=pl.col("usd_gross").fill_null(0),
    )

    # Entropie de Shannon + HHI par wallet sur la part de volume par marché
    tot = m.group_by("address").agg(pl.col("vol").sum().alias("vol_tot"))
    m2 = m.join(tot, on="address").with_columns(
        share=(pl.col("vol") / pl.col("vol_tot")).replace(0, np.nan),
        share2=((pl.col("vol") / pl.col("vol_tot")) ** 2).replace(0, np.nan),
    )
    # entropie = -sum(share * ln(share))  ; ln(share)<0
    m2 = m2.with_columns((-pl.col("share") * pl.col("share").log()).alias("e_i"))
    agg = (m2.group_by("address")
           .agg(
               pl.col("vol").count().alias("n_markets"),
               pl.col("vol_tot").first().alias("usd_gross_mkt"),
               (pl.col("vol").sum()).alias("usd_gross_check"),
               pl.col("share2").sum().alias("hhi"),
               pl.col("e_i").sum().alias("entropy"),
               pl.col("net_cashflow").sum().alias("net_cashflow"),
               (pl.col("net_cashflow") > 0).sum().alias("n_markets_pnl_pos"),
               (pl.col("net_cashflow") < 0).sum().alias("n_markets_pnl_neg"),
               (pl.col("net_cashflow") == 0).sum().alias("n_markets_pnl_zero"),
               pl.col("n").sum().alias("n_trades_mkt"),
           )
           .with_columns(
               win_market_proxy=pl.col("n_markets_pnl_pos") / pl.col("n_markets"),
               roi_cashflow=pl.col("net_cashflow") / pl.col("usd_gross_mkt").replace(0, None),
           ))

    table = prim.join(agg, on="address", how="inner")
    # colonnes de contrôle de cohérence (peuvent diverger : gross inclut BUY+SELL en cashflow)
    n_before = len(prim)
    table.write_parquet(OUT_TABLE)
    summ = {
        "n_wallets_eligible": int(n_before),
        "n_wallets_table": int(len(table)),
        "n_markets_total": int(table["n_markets"].sum()),
        "cols": list(table.columns),
        "out": str(OUT_TABLE),
    }
    (OUTPUT_DIR / "wtable_summary.json").write_text(json.dumps(summ, indent=2))
    print(json.dumps(summ, indent=2))
    return summ


if __name__ == "__main__":
    main()
