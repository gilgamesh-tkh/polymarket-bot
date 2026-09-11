# Rapport — Étape 7e : ajout réseau X4 + interactions (ablation)

Scripts : `16_network_features.py` (X4), `14_supervised_v2.py` (entraînement).

## Features réseau X4 (depuis quant.parquet)
Extraction 1 scan (43,3 M legs, 5,5 min) des legs où maker OU taker ∈ échantillon.
Par wallet : `deg_total` (nb contreparties), `strength_total` ($ échangés), `edges_total`,
`recurrent_total` (paires >1 trade), `recurrence`, `recip` (réciprocité), `avg_edge_usd`.
**Seulement 2 auto-edges (maker==taker)** → quasi aucun self-trade flagrant sur les
wallets de l'échantillon (info pour H2).

## Ablation (CV StratifiedKFold 5×5, n=9 004, positifs H1=99)

| Jeu de features | nb | RF AUC-ROC | XGB AUC-ROC | AUC-PR (XGB) |
|---|---|---|---|---|
| étape 7d : 12 + adv + A+B+C | 41 | **0,938** | 0,928 | 0,260 |
| + réseau X4 | 48 | 0,934 | **0,934** | 0,257 |
| + interactions (5 ratios) | 47 | 0,933 | 0,928 | 0,250 |
| tout (réseau + interactions) | 54 | 0,933 | 0,934 | 0,257 |

## Lecture honnête
- Le **réseau X4** améliore XGB (0,928 → 0,934) et fait entrer `recurrent_total` (2ᵉ) et
  `deg_total` (4ᵉ) dans le top features → signal réel mais **modeste**.
- Les **interactions métier** n'apportent **rien** (bruit ; RF et AUC-PR stables/légère baisse)
  → on les écarte.
- L'AUC-PR plafonne ~0,26 (baseline aléatoire 0,011). Le gain depuis l'étape 7
  (0,172 → 0,26) vient surtout des features comportementales fines (7c/7d), pas du réseau.
- Écarts entre jeux (±0,02) ≈ variance de CV → au-delà de ~48 features, on ajoute du bruit.

## Décision
Modèle retenu : **XGBoost, features 7d + réseau X4 (48 features)** — AUC-ROC 0,934,
AUC-PR 0,257. Le réseau est conservé pour l'interprétation (il caractérise la Smart Money)
même si le gain métrique est faible.

## Top features (XGBoost, jeu final)
frac_token1 · recurrent_total · entropy · deg_total · buy_px_tok1 · hhi · size_cv · hour_entropy
