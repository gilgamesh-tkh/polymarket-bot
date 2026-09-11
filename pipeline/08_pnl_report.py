#!/usr/bin/env python
"""Génère pipeline/output/pnl_report.md à partir de pnl_summary.json + wallet_pnl_wallet.parquet."""
import json
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import OUTPUT_DIR  # noqa: E402

s = json.loads((OUTPUT_DIR / "pnl_summary.json").read_text())
w = pl.read_parquet(OUTPUT_DIR / "wallet_pnl_wallet.parquet")

L = []
p = L.append
p("# Rapport — Étape 5 : PnL réalisé + mark-to-market par wallet")
p("")
p("Méthode : pour chaque (wallet, marché, côté YES/NO) on agrège les BUY (coût) et SELL "
  "(produit) depuis `users_sample.parquet`. `cashflow = proceeds − cost`. Un marché est "
  "**résolu** si `markets.closed=1` et `outcome_prices ∈ {[1,0],[0,1]}` (800 851 marchés). "
  "`pnl_m2m = cashflow + max(inventory,0) × payout` sur les marchés résolus (valorisation "
  "de l'inventaire restant à la résolution). `win_rate` = part de marchés résolus gagnants "
  "(pnl_m2m > 0).")
p("")
p(f"- Wallets dans l'échantillon : **{s['n_wallets']:,}** (sur 10 000 ; 146 sans marché résolu)")
p(f"- PnL mark-to-market positif : {s['n_wallets_pos_pnl_m2m']:,} ({s['pct_pos_m2m']} %)")
p(f"- PnL réalisé pur (cashflow) positif : {s['n_wallets_pos_realized']:,} ({s['pct_pos_realized']} %)")
p(f"- PnL m2m médian : **{s['median_pnl_m2m']:,.0f} $** | ROI m2m médian : "
  f"**{s['median_roi_m2m']*100:.1f} %** | Win rate médian : **{s['median_win_rate']*100:.1f} %**")
p("")
p("### Test des hypothèses H1 (seuils du cahier des charges)")
p("")
p(f"- Wallets avec **ROI > 20 %** : {s['pct_roi_gt20']} % de l'échantillon")
p(f"- Wallets avec **Win Rate > 65 %** : {s['pct_winrate_gt65']} % de l'échantillon")
p("")
p("Interprétation : une minorité (~4 %) dépasse le seuil ROI>20 % ; ~23 % ont un win rate "
  ">65 %. La médiane est négative (ROI −10,9 %) → cohérent avec un marché où la majorité "
  "des traders perd. Ces seuils serviront de *labels candidats* pour le clustering (étape 6).")
p("")
p("### Distribution win_rate (marchés résolus)")
wr = w["win_rate_m2m"].drop_nulls()
import statistics
for lo, hi in [(0, .25), (.25, .5), (.5, .65), (.65, .8), (.8, 1.001)]:
    n = int(((wr >= lo) & (wr < hi)).sum())
    p(f"- [{lo:.2f}, {hi:.2f}[ : {n} wallets ({100*n/len(wr):.1f} %)")
p("")
(OUTPUT_DIR / "pnl_report.md").write_text("\n".join(L))
print("[ok] pipeline/output/pnl_report.md")
