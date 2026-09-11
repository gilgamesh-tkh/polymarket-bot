# Étape 7c — Classifieur enrichi label H1

Population **9,004 wallets**, positifs H1 **99 (1.10 %)**. Features : 12 de base + 8 avancées (profil temporel, sélection de marchés) — 48 au total, aucune fuite.

| Modèle | AUC-ROC | AUC-PR | F1 max |
|---|---|---|---|
| RandomForest (v2) | 0.934±0.022 | 0.176 | 0.254 |
| XGBoost (v2, best) | 0.934±0.020 | 0.257 | 0.278 |

Rappel étape 7 : RF AUC 0,895 / XGB 0,888 ; AUC-PR RF 0,138 / XGB 0,172.

### Top features (XGBoost)

| feature | importance | | feature | importance |
|---|---|---|---|---|
| frac_token1 | 0.106 | | n_markets_resolved | 0.015 |
| recurrent_total | 0.074 | | strength_total | 0.014 |
| entropy | 0.040 | | side_imbalance | 0.014 |
| deg_total | 0.038 | | time_to_end_s | 0.014 |
| buy_px_tok1 | 0.034 | | trades_per_market | 0.014 |
| hhi | 0.034 | | mkt_impact_avg | 0.014 |
| size_cv | 0.031 | | recip | 0.013 |
| hour_entropy | 0.031 | | n_days_active | 0.013 |
| price_range | 0.030 | | n_markets | 0.013 |
| dominant_hour_share | 0.027 | | extremeness | 0.012 |
| usd_gross | 0.026 | | maker_ratio | 0.012 |
| avg_price | 0.026 | | sell_px_tok2 | 0.012 |
| arbitrage_share | 0.025 | | cat_crypto_share | 0.012 |
| sell_px_tok1 | 0.025 | | recurrence | 0.011 |
| avg_usd_trade | 0.023 | | n_weeks_ratio | 0.011 |
| buy_sell_gap_tok1 | 0.021 | | entry_timing_s | 0.010 |
| roundtrip_share | 0.018 | | n_trades | 0.010 |
| first_ts | 0.018 | | mkt_horizon_days_med | 0.010 |
| avg_edge_usd | 0.017 | | mkt_vol_med | 0.010 |
| mkt_impact_med | 0.017 | | weekend_frac | 0.010 |
| cat_politics_share | 0.016 | | span_days | 0.008 |
| edges_total | 0.016 | | vwap | 0.008 |
| buy_px_tok2 | 0.015 | | mkt_negrisk_share | 0.008 |
| buy_sell_gap_tok2 | 0.015 | | cat_sports_share | 0.007 |
