# Étape 8c — Walk-forward multi-coupures (approfondi)

Script : `20_walkforward_grid.py`. Coupures : 2025-03-31 / 06-30 / 09-30 / 12-31.
Protocole identique partout : features sur trades **< C**, label H1 (ROI>20 % & WR>65 %)
sur les marchés débutés **≥ C et résolus** (≥3), population ≥50 trades pré-C. Aucune fuite
temporelle (le réseau X4 est exclu faute de rescan temporel).

## 1. Coupes indépendantes (chaque modèle n'utilise que le passé avant sa coupure)

| Coupure | n | positifs H1 | AUC-ROC (XGB) | AUC-PR |
|---|---|---|---|---|
| 2025-03-31 | 1031 | 58 (5,6 %) | 0,798±0,068 | 0,290 |
| 2025-06-30 | 1207 | 81 (6,7 %) | 0,730±0,056 | 0,261 |
| 2025-09-30 | 1388 | 80 (5,8 %) | 0,735±0,056 | 0,269 |
| 2025-12-31 | 1930 | 98 (5,1 %) | 0,726±0,038 | 0,171 |

**Moyenne : AUC 0,75** — stable (0,73-0,80) → le signal prédictif est **robuste dans le temps**.

## 2. Walk-forward séquentiel STRICT (train → test sans réentraînement)

⚠️ **Purge d'identité** : les wallets présents en entraînement sont **exclus du test**.
Sans cette purge, 72-90 % des wallets du test sont déjà vus en train → le modèle les
"reconnaît" et l'AUC est artificiellement gonflée (0,85-0,91, non reporté ici car biaisé).

| train | test | n_train | n_test (purgé) | positifs test | AUC-ROC | AUC-PR |
|---|---|---|---|---|---|---|
| 2025-03-31 | 2025-06-30 | 1031 | 338 | 9 | 0,691 | 0,112 |
| 2025-06-30 | 2025-09-30 | 1207 | 353 | 7 | 0,750 | 0,273 |
| 2025-09-30 | 2025-12-31 | 1388 | 1019 | 34 | 0,579 | 0,045 |

**AUC moyenne séquentielle purgée : 0,67** (grande variance : seulement 7-34 positifs test).

## 3. Synthèse honnête

- **Borne haute réaliste : AUC ≈ 0,73-0,75** (coupes indépendantes, échantillons plus grands).
- **Borne stricte : AUC ≈ 0,67** (séquentiel purgé, petits échantillons, variance élevée).
- Comparé à la discrimination (~0,93), le vrai pouvoir prédictif est donc **modéré**.
- **Découverte méthodologique clé** : sans purge d'identité, un walk-forward "séquentiel"
  surestime massivement (0,85-0,91) car les mêmes wallets réapparaissent train/test.
  C'est un piège classique à documenter dans le mémoire.

## Limites
- Faible nombre de positifs par fenêtre (7-34) → intervalles de confiance larges.
- Une seule grande coupure possible par manque de données antérieures riches (l'essentiel
  du volume date de 2025-2026).
- Fenêtre de label courte pour les dernières coupures (les marchés doivent se résoudre).
