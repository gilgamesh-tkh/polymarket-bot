# Rapport — Point 2 : Contrôle qualité

Script : `pipeline/01_quality_control.py` + `pipeline/02_dup_check.py`

## quant.parquet

- Lignes : **1,028,646,107** | Row groups : 1,027 | RG triés par temps : False
- Fenêtre : `2022-11-21 19:49:29` → `2026-07-20 14:35:09`  (UTC) — 1331 jours couverts
- `block_number` : 35,896,869 → 90,568,741

### Agrégats (passe complète)

| Variable | min | max | somme | négatifs | nuls |
|---|---|---|---|---|---|
| usd_amount | 0.00 | 6,314,604.37 | 37,761,801,259 | 0 | - |
| token_amount | 0.00 | 6,333,605.19 | 94,929,338,550 | 0 | - |
| price | 0.0 | 0.999199 | (moy 0.4388) | hors [0,1] : **0** | - |
| transaction_hash | - | - | - | - | 0 |
| market_id | - | - | - | - | 0 |

approx distinct tx : 699,794,848 | approx distinct market_id : 1,509,643

### Trous temporels (jours à 0 ligne) : 0
Aucun jour à 0 ligne sur la fenêtre.


## users.parquet

- Lignes : **1,639,420,835** | Row groups : 13,342 | RG triés par temps : True
- Fenêtre : `2022-11-21 19:49:29` → `2026-07-20 14:35:09`  (UTC) — 1331 jours couverts
- `block_number` : 35,896,869 → 90,568,741

### Agrégats (passe complète)

| Variable | min | max | somme | négatifs | nuls |
|---|---|---|---|---|---|
| usd_amount | 0.00 | 6,314,604.37 | 78,502,517,561 | 0 | - |
| token_amount | 0.00 | 14,047,193.90 | 190,494,570,482 | 0 | - |
| price | 0.0 | 7812.67 | (moy 0.5006) | hors [0,1] : **23** | - |
| transaction_hash | - | - | - | - | 0 |
| market_id | - | - | - | - | 0 |

approx distinct tx : 730,742,818 | approx distinct market_id : 1,509,643

### Trous temporels (jours à 0 ligne) : 0
Aucun jour à 0 ligne sur la fenêtre.

## Cohérence inter-fichiers

- `usd_sum` : quant 37,761,801,259 vs users 78,502,517,561 → ratio **2.079** (attendu ≈2 : maker+taker)
- Lignes : quant 1,028,646,107 vs users 1,639,420,835 → ratio 1.594
- Fenêtres temporelles identiques : 2022-11-21 19:49:29 → 2026-07-20 14:35:09
- `approx_distinct_market_id` identiques : 1,509,643

### Détail par jour (volume usd users vs 2×quant)

Ratio journalier `users_count / (2 × quant_count)` : médiane **0.857**, min 0.500, max 1.000 (sur 1331/1331 jours communs).

> Note : le ratio *lignes* ≠ 2 (médiane quotidienne ~0,86) car `users` n'a pas strictement 2 lignes par fill (certains fills mono-leg, granularité différente). Le test de volume décisif est le ratio `usd_sum` ≈ 2,08 ci-dessus — cohérent.

## Doublons (échantillon réservoir)

- **quant** : clé `transaction_hash, log_index` → sur échantillon 1.0 % (10,286,461 lignes) : **0** lignes dans des groupes en double (0 paires, 0 groupes 3+) — taux estimé 0.000000 en 367.2s
- **users** : clé `transaction_hash, log_index, address, role` → sur échantillon 1.0 % (16,394,208 lignes) : **0** lignes dans des groupes en double (0 paires, 0 groupes 3+) — taux estimé 0.000000 en 569.6s

## Anomalies price hors [0,1]

- **users** : 23 lignes `taker/SELL` avec `price`>1 (jusqu'à 7812) — `token_amount` très petits (<~500) pour des `usd_amount` normaux ⇒ `price` = usd/token dégénéré sur des poussières de tokens. À exclure des calculs de PnL/prix (filtre `price BETWEEN 0 AND 1`).
- **quant** : 0 ligne hors [0,1].
