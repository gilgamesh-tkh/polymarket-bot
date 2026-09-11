# Détection Smart Money sur Polymarket

Projet de recherche : détecter les portefeuilles « Smart Money » sur le marché prédictif
Polymarket à partir de l'historique complet des transactions — distinguer le signal
prédictif réel (le passé annonce-t-il les futurs gagnants ?) de la simple
discrimination a posteriori, et tester trois hypothèses (H1 : détectabilité,
H2 : wash trading, H3 : le volume précède le prix sur les longshots).

## Données

Dataset `SII-WANGZJ/Polymarket_data` (fichiers Parquet, **non versionnés** —
plusieurs dizaines de Go) :

| Fichier | Contenu | Volume |
|---|---|---|
| `markets.parquet` | Marchés et résolutions | 1 841 683 lignes |
| `quant.parquet` | Legs de trades (maker + taker) | 1 028 646 107 lignes |
| `users.parquet` | Actions wallet (BUY et SELL) | 1 639 420 835 lignes |

Période couverte : 2022-11-21 → 2026-07-20 (1 331 jours, sans trou temporel).
Placer les fichiers sous `Polymarket_data/data/` (voir `pipeline/config.py`).
Le contrôle qualité a établi : prix `quant` 100 % dans [0, 1], 23 lignes
poussière `price > 1` exclues du PnL, doublons ≈ 0, adresses normalisées en
minuscules, `usd_amount = token_amount × price`.

## Pipeline (`pipeline/`)

25 scripts numérotés (`00_schema_check.py` → `24_make_figures.py`, Python 3.12,
Polars/DuckDB, streaming basse-RAM). Résumés JSON et rapports Markdown générés
dans `pipeline/output/`. Enchaînement :

1. **Schémas & QC** (00–03) — vérification d'environnement, contrôle qualité,
   doublons (échantillon réservoir 1 %), rapport QC.
2. **Wallets** (04–06) — primitives (3 058 883 wallets), éligibilité
   (365 536, 11,95 %, 64,6 G$), échantillon stratifié (n = 10 000, seed 42),
   table finale (10 000 × 31 features X1–X3).
3. **PnL** (07–09) — mark-to-market sur 800 851 marchés binaires résolus, puis
   correction FIFO v2 (les ventes de tokens jamais achetés ne sont plus
   créditées) : ROI médian −11,5 %, 18,3 % de wallets positifs.
4. **Label H1 & modèles** (10–16) — clustering (k = 3, insuffisant seul),
   classifieurs supervisés (RandomForest / XGBoost, 12 → 48 features avec
   timing, exécution, catégories, réseau), **XGB final : AUC-ROC 0,934,
   AUC-PR 0,257** pour 99 positifs H1 (ROI > 20 % et win rate > 65 %, 1,10 %).
5. **Walk-forward** (17–20) — features passées → label futur : AUC-ROC
   **0,742** (features enrichies), 0,73–0,80 sur 4 coupures ; la purge
   d'identité révèle la fuite (séquentiel 0,85–0,91 sans purge → 0,58–0,75
   avec purge).
6. **H2/H3** (21–23) — wash trading (2 auto-échanges ; réciprocité 4,8 % des
   paires / 40,8 % du volume ; suspect 9,1 % ; 4/99 H1 impliqués → **H2
   partiellement soutenue**) ; anomalies de volume sur longshots (P(Δ>15 %)
   5,7 % vs 5,4 % → **H3 non soutenue**).
7. **Figures** (24) — 5 figures du chapitre résultats du mémoire.

Le journal détaillé étape par étape (`pipeline/ETAT_AVANCEMENT.md`) et le
mémoire LaTeX (`latex/`, 65 pages) sont suivis sur la branche `work_on_pd`.

## Dashboard TUI (`dashboard/`)

Application terminal interactive (Textual) de visualisation des résultats —
4 onglets : **Synthèse** des étapes, **PnL & wallets** (stats live recalculées
sur parquet wallet-level), **Modèles ML**, **Hypothèses H1/H2/H3**.

```bash
python -m dashboard
```

Raccourcis : `1`–`4` onglets, `r` recharge l'onglet actif, `q` quitte.

## Notebooks (`notebooks/`)

- `00_ingestion_validation.ipynb` — validation de l'ingestion Parquet.
- `01_exploration.ipynb` — exploration initiale (653 Ko).

## Installation

Python 3.12 recommandé :

```bash
pip install -r requirements.txt
```

Dépendances principales : `polars`, `duckdb`, `pandas`, `numpy`,
`scikit-learn`, `xgboost`, `matplotlib`, `textual` (dashboard), `pyyaml`,
`click`. Un environnement `polyenv/` est fourni à titre indicatif.

## Structure du dépôt (branche `main`)

```
.
├── dashboard/          # Application TUI Textual (app, data, views)
├── pipeline/           # Scripts 00–24 + sorties (output/*.json, *.md)
├── notebooks/          # Notebooks d'ingestion et d'exploration
├── config/             # config.yaml, model_config.yaml (sans secrets)
├── docs/               # Documentation (voir .gitignore)
├── requirements.txt    # Dépendances Python
├── setup.py            # Packaging
└── LICENSE             # Licence
```

Exclus du versionnement sur `main` (volumineux ou hors périmètre public) :
données brutes (`data/`, `processed/`, `Polymarket_data/`), mémoire LaTeX
(`latex/`), journal d'avancement (`pipeline/ETAT_AVANCEMENT.md`,
`rapport_avancement-poly_data.md`) et fichiers de structure
(`PROJECT_STRUCTURE.md`). Voir `.gitignore`.

## Licence

Voir `LICENSE`.
