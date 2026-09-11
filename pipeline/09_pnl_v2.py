#!/usr/bin/env python
"""Étape 5 (v2) — PnL corrigé : pas de profit fictif sur les ventes pré-fenêtre.

Théorie :
  Pour une paire (wallet, market, side), si le cumul des ventes ne dépasse JAMAIS le cumul
  des achats (jamais en position courte), alors le PnL total est, méthode-indépendant :
      pnl = proceeds_sells + held×payout − cost_buys ,  held = (buys − sells) ≥ 0
  (== v1, exacte).

  Si le groupe passe en déficit (cum_sell > cum_buy à un instant), certaines ventes portent
  sur des tokens acquis HORS fenêtre (mintés) : leur coût est inconnu → on les retire du
  calcul. On refait alors une attribution FIFO stricte en Python :
      à chaque vente, on ne crédite que min(vente, inventaire courant) ; l'excédent est ignoré.
      pnl = attributed_proceeds + held×payout − cost_buys_totaux

Sorties : wallet_pnl_v2.parquet (par wallet×market), wallet_pnl_wallet_v2.parquet,
          pnl_v2_summary.json
"""
import json
import sys
import time
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import OUTPUT_DIR  # noqa: E402


def fifo_attribution(g):
    """Attribue FIFO ventes→achats. Retourne (attributed_proceeds, held)."""
    qb = g["qb"].to_numpy()
    qs = g["qs"].to_numpy()
    ub = g["usd_b"].to_numpy()
    us = g["usd_s"].to_numpy()
    inv = 0.0
    att_S = 0.0
    att_P = 0.0
    for b, s, cb, cs in zip(qb, qs, ub, us):
        if b > 0:
            inv += b
        if s > 0:
            take = min(s, inv)
            if take > 0:
                price = cs / s if s else 0.0
                att_S += take
                att_P += take * price
                inv -= take
    return att_P, inv  # inv = held final


def main():
    t0 = time.time()
    resolved = (pl.read_parquet(OUTPUT_DIR / "market_resolved.parquet")
                .select(["id", "winner", "payout1", "payout2"]).rename({"id": "market_id"}))

    cols = ["address", "market_id", "nonusdc_side", "timestamp", "direction",
            "usd_amount", "token_amount"]
    ev = (pl.read_parquet(OUTPUT_DIR / "users_sample.parquet", columns=cols)
          .with_columns(
              qb=pl.when(pl.col("direction") == "BUY").then(pl.col("token_amount")).otherwise(0.0),
              qs=pl.when(pl.col("direction") == "SELL").then(pl.col("token_amount")).otherwise(0.0),
              usd_b=pl.when(pl.col("direction") == "BUY").then(pl.col("usd_amount")).otherwise(0.0),
              usd_s=pl.when(pl.col("direction") == "SELL").then(pl.col("usd_amount")).otherwise(0.0))
          .drop(["direction", "usd_amount", "token_amount"])
          .sort(["address", "market_id", "nonusdc_side", "timestamp"]))
    print(f"events {len(ev):,} ({time.time()-t0:.0f}s)")

    # détection déficit par groupe
    ev = ev.with_columns([
        pl.col("qb").cum_sum().over(["address", "market_id", "nonusdc_side"]).alias("c_buy"),
        pl.col("qs").cum_sum().over(["address", "market_id", "nonusdc_side"]).alias("c_sell"),
    ]).with_columns(deficit=pl.col("c_sell") - pl.col("c_buy"))
    had = (ev.group_by(["address", "market_id", "nonusdc_side"])
           .agg((pl.col("deficit") > 1e-9).any().alias("had_deficit")))
    n_def = had.filter(pl.col("had_deficit")).height
    print(f"groupes avec déficit : {n_def} ({time.time()-t0:.0f}s)")

    # ---- groupes PROPRES (jamais déficit) : formule agrégée exacte ----
    clean_keys = had.filter(~pl.col("had_deficit")).drop("had_deficit")
    clean = ev.join(clean_keys, on=["address", "market_id", "nonusdc_side"])
    agg = (clean.group_by(["address", "market_id", "nonusdc_side"])
           .agg(pl.col("qb").sum().alias("B"),
                pl.col("qs").sum().alias("S"),
                pl.col("usd_b").sum().alias("C"),
                pl.col("usd_s").sum().alias("P"))
           .with_columns(held=(pl.col("B") - pl.col("S")).clip(lower_bound=0.0),
                         att_P=pl.col("P")))
    print(f"paires propres {agg.height:,} ({time.time()-t0:.0f}s)")

    # ---- groupes DÉFICIT : FIFO Python ----
    def_keys = had.filter(pl.col("had_deficit")).drop("had_deficit")
    fix_rows = []
    if def_keys.height:
        sub = ev.join(def_keys, on=["address", "market_id", "nonusdc_side"])
        for (address, market_id, side), g in sub.group_by(["address", "market_id", "nonusdc_side"]):
            g = g.sort("timestamp")
            att_P, held = fifo_attribution(g)
            B = float(g["qb"].sum())
            C = float(g["usd_b"].sum())
            fix_rows.append({"address": address, "market_id": market_id,
                             "nonusdc_side": side, "B": B, "C": C, "att_P": att_P,
                             "held": held})
    fix = pl.DataFrame(fix_rows)
    print(f"paires déficit traitées {fix.height:,} ({time.time()-t0:.0f}s)")

    # ---- concat + pivot par side ----
    keep_common = ["address", "market_id", "nonusdc_side", "B", "C", "att_P", "held"]
    allp = pl.concat([agg.select(keep_common), fix.select(keep_common)])
    p1 = (allp.filter(pl.col("nonusdc_side") == "token1").drop("nonusdc_side")
          .rename({"B": "B1", "C": "C1", "att_P": "P1", "held": "held1"}))
    p2 = (allp.filter(pl.col("nonusdc_side") == "token2").drop("nonusdc_side")
          .rename({"B": "B2", "C": "C2", "att_P": "P2", "held": "held2"}))
    wm = (p1.join(p2, on=["address", "market_id"], how="full")
          .with_columns([pl.col(c).fill_null(0.0) for c in
                         ["B1", "C1", "P1", "held1", "B2", "C2", "P2", "held2"]]))
    wm = wm.join(resolved, on="market_id", how="left").with_columns(
        resolved=pl.col("winner").is_not_null(),
    ).with_columns(
        pnl=((pl.col("P1") - pl.col("C1") + pl.col("held1") * pl.col("payout1").fill_null(0.0))
             + (pl.col("P2") - pl.col("C2") + pl.col("held2") * pl.col("payout2").fill_null(0.0))),
        realized=(pl.col("P1") - pl.col("C1")) + (pl.col("P2") - pl.col("C2")),
    ).with_columns(
        pnl_resolved=pl.when(pl.col("resolved")).then(pl.col("pnl")).otherwise(None),
    )
    keep = ["address", "market_id", "B1", "C1", "P1", "held1", "B2", "C2", "P2", "held2",
            "resolved", "winner", "realized", "pnl", "pnl_resolved"]
    wm.select(keep).write_parquet(OUTPUT_DIR / "wallet_pnl_v2.parquet")
    print(f"wallet×market {wm.height:,} écrit ({time.time()-t0:.0f}s)")

    # ---- agrégation wallet ----
    wr = (wm.filter(pl.col("resolved"))
          .group_by("address")
          .agg((pl.col("pnl_resolved") > 0).sum().alias("n_resolved_won"),
               (pl.col("pnl_resolved") < 0).sum().alias("n_resolved_lost"),
               pl.col("pnl_resolved").count().alias("n_markets_resolved"))
          .with_columns(win_rate_m2m=pl.col("n_resolved_won") / pl.col("n_markets_resolved")))
    w = (wm.group_by("address")
         .agg(pl.col("market_id").count().alias("n_markets_traded"),
              pl.col("pnl").sum().alias("pnl"),
              pl.col("realized").sum().alias("realized"),
              (pl.col("pnl_resolved")).sum().alias("pnl_resolved"),
              pl.col("C1").sum().alias("C1"), pl.col("C2").sum().alias("C2"),
              pl.col("P1").sum().alias("P1"), pl.col("P2").sum().alias("P2"))
         .with_columns(total_cost=pl.col("C1") + pl.col("C2"),
                       total_proceeds=pl.col("P1") + pl.col("P2"))
         .with_columns(roi=pl.col("pnl") / pl.col("total_cost").replace(0, None),
                       roi_resolved=pl.col("pnl_resolved") / pl.col("total_cost").replace(0, None))
         .join(wr, on="address", how="left"))
    w.write_parquet(OUTPUT_DIR / "wallet_pnl_wallet_v2.parquet")

    s = {
        "n_wallets": int(w.height),
        "n_pos_pnl": int((w["pnl"] > 0).sum()),
        "pct_pos_pnl": round(100 * (w["pnl"] > 0).mean(), 2),
        "median_pnl": float(w["pnl"].median()),
        "median_roi": float(w["roi"].median()),
        "median_win_rate": float(w["win_rate_m2m"].median()),
        "pct_roi_gt20": round(100 * (w["roi"] > 0.20).mean(), 2),
        "pct_winrate_gt65": round(100 * (w["win_rate_m2m"] > 0.65).mean(), 2),
    }
    (OUTPUT_DIR / "pnl_v2_summary.json").write_text(json.dumps(s, indent=2))
    print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()
