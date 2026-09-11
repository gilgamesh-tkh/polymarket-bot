# Rapport — Point 1 : vérification de l'environnement et des schémas

## quant.parquet  (36.68 Go)

### Fichier localisé
- Chemin : `/media/lrh/theProwler/Project/mem/Polymarket_data/data/quant.parquet`

### Schéma réel (DuckDB)

| # | colonne | type |
|---|---------|------|
| 0 | timestamp | UBIGINT |
| 1 | block_number | UBIGINT |
| 2 | transaction_hash | VARCHAR |
| 3 | log_index | UINTEGER |
| 4 | market_id | VARCHAR |
| 5 | condition_id | VARCHAR |
| 6 | event_id | VARCHAR |
| 7 | price | DOUBLE |
| 8 | usd_amount | DOUBLE |
| 9 | token_amount | DOUBLE |
| 10 | side | VARCHAR |
| 11 | maker | VARCHAR |
| 12 | taker | VARCHAR |

### Divergences vs schéma documenté
- Colonnes documentées absentes : `['datetime']`
- Colonnes réelles non documentées : `['condition_id', 'event_id', 'log_index', 'maker', 'side', 'taker', 'timestamp']`
- Doc : `datetime` → réel : `timestamp` (UBIGINT epoch).
- Doc : `transaction_hash`,`market_id` présents ; réels ajoutés : `log_index`, `condition_id`, `event_id`, `side`, `maker`, `taker`.

### head()
```
                                                          0                                          1                                          2
timestamp                                        1669162229                                 1669162433                                 1669162849
block_number                                       35945792                                   35945888                                   35946048
transaction_hash  b308ecde64d4f4f4d8c148da0c9391abd4fa34...  894bf03e8e512e94d033910bff5370efdf317b...  8e57248f1245afdf82c714900f0dd3510115c8...
log_index                                               459                                        153                                        433
market_id                                            240380                                     240380                                     240380
condition_id      0x41190eb9336ae73949c04f4900f9865092e6...  0x41190eb9336ae73949c04f4900f9865092e6...  0x41190eb9336ae73949c04f4900f9865092e6...
event_id                                               5828                                       5828                                       5828
price                                                   0.5                                       0.95                                       0.95
usd_amount                                              0.5                                       0.75                                        0.5
token_amount                                            1.0                                       15.0                                       10.0
side                                                   SELL                                        BUY                                        BUY
maker             0xEA5981CA48Dc40C950fC1B2496c4a0Ef900b...  0x388911E52Bb2EB440B9f03eD24bcef13C93E...  0x388911E52Bb2EB440B9f03eD24bcef13C93E...
taker             0x388911E52Bb2EB440B9f03eD24bcef13C93E...  0x388911E52Bb2EB440B9f03eD24bcef13C93E...  0x388911E52Bb2EB440B9f03eD24bcef13C93E...
```

## users.parquet  (47.69 Go)

### Fichier localisé
- Chemin : `/media/lrh/theProwler/Project/mem/Polymarket_data/data/users.parquet`

### Schéma réel (DuckDB)

| # | colonne | type |
|---|---------|------|
| 0 | timestamp | UBIGINT |
| 1 | block_number | UBIGINT |
| 2 | transaction_hash | VARCHAR |
| 3 | log_index | UINTEGER |
| 4 | address | VARCHAR |
| 5 | role | VARCHAR |
| 6 | direction | VARCHAR |
| 7 | usd_amount | DOUBLE |
| 8 | token_amount | DOUBLE |
| 9 | price | DOUBLE |
| 10 | market_id | VARCHAR |
| 11 | condition_id | VARCHAR |
| 12 | event_id | VARCHAR |
| 13 | nonusdc_side | VARCHAR |

### Divergences vs schéma documenté
- Colonnes documentées absentes : `['datetime', 'user']`
- Colonnes réelles non documentées : `['address', 'condition_id', 'direction', 'event_id', 'log_index', 'nonusdc_side', 'timestamp']`
- Doc : `user` → réel : `address`. `datetime` → `timestamp` (UBIGINT).
- Réels ajoutés : `log_index`, `condition_id`, `event_id`, `direction`, `nonusdc_side`.
- **Attention** : `direction` réel contient BUY *et* SELL (contrairement à la doc « unifiée BUY »).

### head()
```
                                                          0                                          1                                          2
timestamp                                        1669060169                                 1669060373                                 1669060582
block_number                                       35896869                                   35896929                                   35897058
transaction_hash  05a7f9b0b016d7e431b4e62b374870a91a8d86...  3a5412c9d8129e8a27ddb43cdf60ada4df1a41...  4541524b5b2f910c9f3f5d12feae26d366dcb4...
log_index                                               204                                        161                                        189
address           0xea5981ca48dc40c950fc1b2496c4a0ef900b...  0xea5981ca48dc40c950fc1b2496c4a0ef900b...  0xea5981ca48dc40c950fc1b2496c4a0ef900b...
role                                                  maker                                      maker                                      maker
direction                                               BUY                                        BUY                                        BUY
usd_amount                                             50.0                                       60.0                                        5.0
token_amount                                          100.0                                      100.0                                       10.0
price                                                   0.5                                        0.6                                        0.5
market_id                                            240380                                     240380                                     240380
condition_id      0x41190eb9336ae73949c04f4900f9865092e6...  0x41190eb9336ae73949c04f4900f9865092e6...  0x41190eb9336ae73949c04f4900f9865092e6...
event_id                                               5828                                       5828                                       5828
nonusdc_side                                         token1                                     token1                                     token1
```

## markets.parquet  (0.29 Go)

### Fichier localisé
- Chemin : `/media/lrh/theProwler/Project/mem/Polymarket_data/data/markets.parquet`

### Schéma réel (DuckDB)

| # | colonne | type |
|---|---------|------|
| 0 | id | VARCHAR |
| 1 | question | VARCHAR |
| 2 | slug | VARCHAR |
| 3 | condition_id | VARCHAR |
| 4 | token1 | VARCHAR |
| 5 | token2 | VARCHAR |
| 6 | answer1 | VARCHAR |
| 7 | answer2 | VARCHAR |
| 8 | closed | UTINYINT |
| 9 | active | UTINYINT |
| 10 | archived | UTINYINT |
| 11 | outcome_prices | VARCHAR |
| 12 | volume | DOUBLE |
| 13 | event_id | VARCHAR |
| 14 | event_slug | VARCHAR |
| 15 | event_title | VARCHAR |
| 16 | created_at | TIMESTAMP WITH TIME ZONE |
| 17 | end_date | TIMESTAMP WITH TIME ZONE |
| 18 | updated_at | TIMESTAMP WITH TIME ZONE |
| 19 | neg_risk | UTINYINT |

### Divergences vs schéma documenté
- Colonnes réelles non documentées : `['neg_risk']`
- 20 colonnes réelles (id, question, slug, condition_id, token1/2, answer1/2, closed, active, archived, outcome_prices, volume, event_id, event_slug, event_title, created_at, end_date, updated_at, neg_risk).

### head()
```
                                                        0                                          1                                          2
id                                                2099572                                    2099573                                    2099574
question        Will Emmanuel Macron be the next leade...  Will Recep Tayyip Erdoğan be the next ...  Will Kim Jong Un be the next leader ou...
slug            will-emmanuel-macron-be-the-next-leade...  will-recep-tayyip-erdoan-be-the-next-l...  will-kim-jong-un-be-the-next-leader-ou...
condition_id    0x2da5c3a8740d8b942d6052a34af61fe52105...  0x765ef48156d3cf6c52562cc2b59def66c713...  0xa8e9566651e959f6b5807a45d8e89f2eb123...
token1          68828132072794158002800116725673730425...  32355359926292808803452420719521491167...  56121656291568559177384650111592024880...
token2          91879727002147272363360227516907986149...  80838652440770406265560536032022668469...  96728453637742520286931110346029055045...
answer1                                               Yes                                        Yes                                        Yes
answer2                                                No                                         No                                         No
closed                                                  1                                          1                                          1
active                                                  1                                          1                                          1
archived                                                0                                          0                                          0
outcome_prices                       ['0.0005', '0.9995']                       ['0.0005', '0.9995']                       ['0.0005', '0.9995']
volume                                      242790.121008                              260384.640718                              209632.393176
event_id                                           424982                                     424982                                     424982
event_slug      next-leader-out-of-power-before-2027-n...  next-leader-out-of-power-before-2027-n...  next-leader-out-of-power-before-2027-n...
event_title     Next leader out of power before 2027? ...  Next leader out of power before 2027? ...  Next leader out of power before 2027? ...
created_at                      2026-04-27 21:12:56+02:00                  2026-04-27 21:12:57+02:00                  2026-04-27 21:12:58+02:00
end_date                        2026-12-31 01:00:00+01:00                  2026-12-31 01:00:00+01:00                  2026-12-31 01:00:00+01:00
updated_at                      2026-07-20 15:31:45+02:00                  2026-07-20 15:31:45+02:00                  2026-07-20 15:31:45+02:00
neg_risk                                                1                                          1                                          1
```

## Notes de jointure

- `quant.market_id` (échantillon) : VARCHAR
- `quant.id` (échantillon) : VARCHAR
- `quant.condition_id` (échantillon) : VARCHAR
- `quant.event_id` (échantillon) : VARCHAR
- `markets.id` (échantillon) : VARCHAR
- `markets.condition_id` (échantillon) : VARCHAR