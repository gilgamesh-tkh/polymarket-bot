# Rapport — Étape 5 (v2) : PnL corrigé (attribution FIFO temporelle)

Script : `pipeline/09_pnl_v2.py`. Sorties : `wallet_pnl_v2.parquet`, `wallet_pnl_wallet_v2.parquet`.

## Problème corrigé (v1)
La v1 créditait comme profit **toutes** les ventes (`proceeds − cost`), y compris celles de
tokens **jamais achetés dans la fenêtre** (inventaire net < 0) : des market makers qui
vendent des tokens *mintés* (dépôt USDC → paire YES/NO) ou détenus avant nov. 2022.
Ces ventes n'ont pas de coût de revient observable → la v1 fabriquait du PnL fictif.

## Méthode v2
- Détection par (wallet, market, side) des groupes passant en **déficit** (cumul des ventes
  > cumul des achats à un instant) via cumul temporel : **112 239 paires** sur 6,2 M (1,8 %),
  touchant des market makers.
- Groupes propres (jamais en déficit, 98,2 %) : formule agrégée **exacte et
  méthode-indépendante** `pnl = proceeds + held×payout − cost` avec `held = max(buys−sells,0)`.
- Groupes en déficit : **attribution FIFO stricte** en Python (tri temporel) ; une vente
  n'est créditée que jusqu'à `min(vente, inventaire courant)` — l'excédent (tokens
  pré-fenêtre) est ignoré car de coût inconnu.
- PnL = `attributed_proceeds + held×payout − cost_buys` ; valorisation à la résolution
  (`outcome_prices ∈ {[1,0],[0,1]}`), `held` = tokens encore détenus.

## Impact (v1 → v2, n = 9 854 wallets)
- PnL médian : **−187 $ → −199 $** ; ROI médian : **−10,9 % → −11,5 %**
- Wallets positifs : **19,6 % → 18,3 %**
- **387 wallets** avec |ΔPnL| > 100 $ ; **139** > 1 000 $ ; **161** changements de signe
- Cas extrême : wallet `0xe372…b38` : v1 = **+12,93 M$** (fictif) → v2 = **−15 $**
- Corrélation PnL v1-v2 : 0,96 ; win rate : 0,98 → la correction est **ciblée** (market makers),
  pas un changement global.

## Synthèse v2 (seuils H1)
- ROI > 20 % : **3,15 %** (vs 3,95 % v1) | Win Rate > 65 % : **21,9 %** (vs 22,7 % v1)

## Limites restantes
- Tokens mintés avant la fenêtre encore **détenus** à la fin : valorisés au payout (ok), mais
  leur coût d'origine (≈0,5/pair) n'est pas soustrait → léger biais haussier résiduel.
- Redemptions hors `users` (OrderFilled seulement) : gérées implicitement via valorisation
  `held×payout` à la résolution.
- Marchés non binaires exclus ; win rate = proportion de marchés résolus gagnants (non pondéré).
