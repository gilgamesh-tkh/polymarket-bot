# Rapport — Étape 5 : PnL réalisé + mark-to-market par wallet

Méthode : pour chaque (wallet, marché, côté YES/NO) on agrège les BUY (coût) et SELL (produit) depuis `users_sample.parquet`. `cashflow = proceeds − cost`. Un marché est **résolu** si `markets.closed=1` et `outcome_prices ∈ {[1,0],[0,1]}` (800 851 marchés). `pnl_m2m = cashflow + max(inventory,0) × payout` sur les marchés résolus (valorisation de l'inventaire restant à la résolution). `win_rate` = part de marchés résolus gagnants (pnl_m2m > 0).

- Wallets dans l'échantillon : **9,855** (sur 10 000 ; 146 sans marché résolu)
- PnL mark-to-market positif : 1,928 (19.56 %)
- PnL réalisé pur (cashflow) positif : 468 (4.75 %)
- PnL m2m médian : **-187 $** | ROI m2m médian : **-10.9 %** | Win rate médian : **47.2 %**

### Test des hypothèses H1 (seuils du cahier des charges)

- Wallets avec **ROI > 20 %** : 3.95 % de l'échantillon
- Wallets avec **Win Rate > 65 %** : 22.7 % de l'échantillon

Interprétation : une minorité (~4 %) dépasse le seuil ROI>20 % ; ~23 % ont un win rate >65 %. La médiane est négative (ROI −10,9 %) → cohérent avec un marché où la majorité des traders perd. Ces seuils serviront de *labels candidats* pour le clustering (étape 6).

### Distribution win_rate (marchés résolus)
- [0.00, 0.25[ : 1580 wallets (17.5 %)
- [0.25, 0.50[ : 3211 wallets (35.7 %)
- [0.50, 0.65[ : 2159 wallets (24.0 %)
- [0.65, 0.80[ : 1035 wallets (11.5 %)
- [0.80, 1.00[ : 1019 wallets (11.3 %)
