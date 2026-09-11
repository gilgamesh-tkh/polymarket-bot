# Étape 7 — Classifieur supervisé label H1 (Smart Money)

Population : **9,004 wallets** (≥1 marché résolu), positifs H1 = **99 (1.10 %)**.

Label H1 : `(roi > 0.20) & (win_rate_m2m > 0.65)`. Features **sans fuite** (aucune variable dérivée du PnL/ROI/win rate n'est utilisée) :

`n_trades, maker_ratio, avg_usd_trade, usd_gross, n_markets, n_markets_resolved, n_days_active, span_days, hhi, entropy, avg_price, vwap`

Évaluation : StratifiedKFold 5-fold **répété 5×** (25 splits), features standardisées. Baseline aléatoire = AUC 0,50 / AUC-PR = prévalence (1,1 %).

| Modèle | AUC-ROC (μ±σ) | AUC-PR (μ±σ) | Meilleur F1 |
|---|---|---|---|
| RandomForest | 0.895±0.032 | 0.138±0.036 | 0.229 |
| XGBoost | 0.888±0.030 | 0.172±0.058 | 0.262 |

AUC-PR d'un classifieur naïf = prévalence ≈ 1,1 % ; un bon modèle doit nettement dépasser ~0,01 en AUC-PR.

### Importance des features (RandomForest → XGBoost)

| feature | RF | XGB |
|---|---|---|
| avg_price | 0.183 | 0.175 |
| avg_usd_trade | 0.126 | 0.121 |
| vwap | 0.103 | 0.057 |
| n_markets_resolved | 0.102 | 0.083 |
| entropy | 0.086 | 0.089 |
| n_trades | 0.077 | 0.098 |
| n_markets | 0.073 | 0.078 |
| hhi | 0.069 | 0.058 |
| maker_ratio | 0.057 | 0.068 |
| usd_gross | 0.049 | 0.060 |
| n_days_active | 0.044 | 0.062 |
| span_days | 0.030 | 0.051 |

### Limites méthodologiques

- **Cross-sectionnel** : le label H1 est calculé sur toute la fenêtre ; l'AUC mesure la *discriminabilité* (peut-on repérer un wallet rentable à partir de son comportement agrégé), PAS la *prédictibilité* (le comportement PASSE-t-il avant le résultat ?).
- Pour une vraie validation prédictive, il faudra un **walk-forward** (features sur [t0, t1] → label sur [t1, t2]) — étape ultérieure.
- Déséquilibre extrême (1,1 %) : l'AUC-ROC peut être optimiste en présence de grande variance ; l'AUC-PR est la métrique la plus informative ici.