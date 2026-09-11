# Étape 6 — Analyse du clustering & croisement H1

Population : **9,004 wallets** éligibles avec ≥1 marché résolu. Features comportementales : ROI, win rate, nb marchés résolus, ratio maker, nb trades, jours actifs, taille moyenne de trade, nb marchés, HHI, entropie (log1p sur les compteurs, standardisation).

## K-Means — robustesse au choix de k

| k | silhouette | calinski-harabasz |
|---|---|---|
| 3 | 0.2551 | 2527 |
| 4 | 0.1651 | 2131 |
| 5 | 0.1500 | 1884 |
| 6 | 0.1529 | 1753 |
| 7 | 0.1462 | 1659 |
| 8 | 0.1532 | 1587 |

Meilleur k selon silhouette : **k=3** (0.2551). Silhouette faible (<0.25) → les wallets forment un **continuum**, pas des clusters nets : attendu en données financières.

## DBSCAN — sensibilité à eps (min_samples=20)

| eps | clusters | bruit (%) |
|---|---|---|
| 0.3 | 2 | 99.0 % |
| 0.5 | 13 | 93.9 % |
| 0.7 | 15 | 80.4 % |
| 1.0 | 6 | 44.7 % |
| 1.5 | 2 | 7.9 % |

DBSCAN ne trouve pas de structure dense nette : à eps faible tout est bruit, à eps fort les clusters fusionnent. Cohérent avec le continuum observé.

## Croisement avec le label H1 (ROI>20 % & WinRate>65 %)

Wallets vérifiant H1 : **99 (1.10 %)**

| cluster | n | n_H1 | %H1 | roi médian | winrate médian |
|---|---|---|---|---|---|
| 0 | 2,537 | 58 | 2.3 % | -0.063 | 0.381 |
| 1 | 1,884 | 2 | 0.1 % | -0.151 | 0.520 |
| 2 | 717 | 22 | 3.1 % | -0.003 | 0.450 |
| 3 | 2,649 | 17 | 0.6 % | -0.067 | 0.429 |
| 4 | 1,217 | 0 | 0.0 % | -0.155 | 0.539 |

Part H1 globale : 1.10 %. Meilleur cluster : **3.1 %** (lift 2.79×).

## Conclusion

- Le clustering (K-Means ou DBSCAN) ne sépare **pas** un groupe 'Smart Money' nettement : la structure dominante est la **taille/intensité d'activité** (petits vs gros traders / makers), pas la performance.
- Le meilleur cluster H1 n'atteint qu'un lift modeste (≤~2×) : les wallets rentables (ROI>20 % & WR>65 %) restent rares et dispersés → cohérent avec l'hypothèse d'une petite minorité, mais le clustering non supervisé seul ne suffit pas à les isoler.
- **Recommandation** : passer à une approche **supervisée/semi-supervisée** (label H1 + RandomForest/XGBoost, ou Isolation Forest sur les résidus) plutôt que clustering pur. Le clustering servira de features d'analyse, pas de label.