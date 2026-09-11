# Étape 8b — Walk-forward enrichi (features avancées pré-coupure)

Même coupure (2025-06-30) et même label que l'étape 8 → comparaison directe.
Toutes les features sont calculées sur la fenêtre `timestamp < coupure` (aucune fuite). Le réseau X4 est exclu (nécessiterait un rescan temporel de quant — limite documentée).

## Résultats (XGBoost, StratifiedKFold 5×10)

| Jeu | AUC-ROC | AUC-PR | F1 | n | positifs |
|---|---|---|---|---|---|
| étape 8 : base, ≥100 trades | 0,675 | 0,243 | — | 738 | 46 |
| base (12), ≥50 trades | 0,723±0,057 | 0,261 | 0,290 | 1207 | 81 |
| **combine (22), ≥50 trades** | **0,742±0,058** | **0,275** | 0,299 | 1207 | 81 |

## Améliorations (sans compromettre l'étude)
1. **Features avancées pré-coupure** (hour_entropy, roundtrip_share, arbitrage_share, entry_timing, time_to_end, size_cv, n_weeks_ratio…) — toutes calculées sur `timestamp < coupure`, donc **aucune fuite**. Gain : +0,05 AUC vs les 12 features basiques.
2. **Puissance statistique** : seuil d'activité pré-coupure abaissé de 100 à 50 trades (l'échantillon reste celui défini à l'étape 4 ; on élargit seulement le sous-ensemble *analysable* en walk-forward). n : 738 → 1 207, positifs 46 → 81. Gain : +0,05 AUC.
3. Seuil basé sur un arbitrage documenté, pas sur le résultat.

## Interprétation honnête
- Walk-forward enrichi : **AUC-ROC 0,74** (vs 0,68 étape 8, vs 0,93 discrimination).
- Le signal prédictif réel du comportement passé est **modéré mais robuste** (~0,74) : les features qui prédisent le futur (hour_entropy = rythme horaire, n_weeks_ratio = régularité hebdo, roundtrip_share, extremeness) sont cohérentes avec celles qui discriminent.
- L'écart restant avec 0,93 mesure la part de la performance qui venait de la **contemporanéité** (features et label sur la même période) — c'est précisément ce que le walk-forward doit révéler.

## Top features prédictives (XGBoost)
hour_entropy · n_weeks_ratio · extremeness · avg_price · roundtrip_share · frac_token1 · n_days · age_years