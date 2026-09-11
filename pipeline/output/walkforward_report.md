# Étape 8 — Walk-forward : le passé prédit-il le futur ?

**Coupure** : trades < `2025-06-30` pour les features ; label = H1 (ROI>20 % & WinRate>65 %) sur les marchés débutés après la coupure et résolus.

### Résultat

| Modèle | AUC-ROC | AUC-PR | F1 max |
|---|---|---|---|
| RandomForest | 0.696±0.105 | 0.249 | 0.294 |
| XGBoost | 0.676±0.099 | 0.250 | 0.288 |

Population : **738 wallets** (comportement ≥100 trades avant coupure ET ≥3 marchés résolus après), dont **46 positifs H1 futurs (6.2 %)**.

### Comparaison avec la discrimination (étape 7e)

- Discrimination (label et features sur la même période) : AUC-ROC ≈ **0,93**
- **Walk-forward (features passées → label futur) : AUC-ROC ≈ 0.68**

L'écart mesure la **part de signal réellement prédictif** vs la part qui vient de la contemporanéité (comportement et résultat mesurés ensemble).
