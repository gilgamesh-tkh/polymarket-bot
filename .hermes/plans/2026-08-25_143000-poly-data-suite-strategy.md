# poly_data — Plan de travail pour une stratégie Polymarket

> **Pour Hermes :** lecture seule ici. Ce plan n’est pas un plan d’implémentation unitaire, mais une feuille de route produit / technique.

**Objectif :** partir du repo `poly_data` tel qu’il est pour construire une base d’analyse exploitable sur Polymarket et, si besoin, exposer un métaboliseur de données à un agent ou un workspace.

**Architecture cible :** pipeline v2 stable + couche d’analyse / intégration distincte.

---

## 1. Hypothèses de départ (à valider en 10 min)

- Le repo est déjà cloné dans `/home/lrh/Bureau/Project/mem/poly_data`.
- Le pipeline v2 fonctionne avec un token HyperSync valide dans `.env`.
- L’objectif prioritaire est **l’analyse** (volume, edge, comportamento utilisateurs), pas la refonte du scraper.

## 2. Phases proposées

### Phase 1 — Vérifier et stabiliser la base (30–60 min)

**2.1 Installer le projet**

```
cd /home/lrh/Bureau/Project/mem/poly_data
python3 -m venv .venv && source .venv/bin/activate
pip install uv && uv sync
```

**2.1 Valider le pipeline**

- Vérifier la présence du tests : `uv run pytest`
- Premier lancement : `uv run poly-data` (ce sera long la premiere fois : backfill complet sur HyperSync)
- Checker que `data/markets.csv`, `data/orderFilled.csv` et `processed/trades.csv` ont été générés

**2.2 Documenter l’état courant**

- Ouvrir `data/cursor_state.json` et `data/markets_state.json` pour connaître le dernier block scanné
- Écrire un court `STATUS.md` dans le repo : token utilisé, date du dernier run, volume de données, points bloquants

### Phase 2 — Explorer les données (1–2 h)

**2.3 Notebook de cadrage**

- Créer `notebooks/exploration.ipynb` (gitignoré ou versionné avec `--no-index`)
- Charger `processed/trades.csv` avec `polars` (voir README.md pour le snippet de base)
- Répondre à 5 questions métier, par ex :
  1. Quels sont les 10 markets les plus traités ?
  2. Quel est le profil de volume horaire/jour ?
  3. Y a-t-il des tokens jamais crossés sur certains marchés ?
  4. Qui sont les 20 makers les plus actifs (volume cumulé) ?
  5. Quel est le win rate / PnL moyen d’un wallet donné (si on arrive à reconstruire les positions) ?

**2.4 Cartographie des acteurs**

- Produire un petit fichier `analysis/traders.csv` avec : address, nb trades, volume total USD, première / dernière activité, nb markets distincts
- Exposer adresses / slugs connus dans `config/traders.yaml` pour les suivis futurs

### Phase 3 — Normalisation et intégration (2–4 h)

**3.1 Schéma propre**

- Pour l’instant, `trades.csv` est le output « brut normalisé ». Produire une version analytique mieux typée :
  - `datetime` (UTC) → colonne dérivée `date`, `hour`, `dow`
  - `token_amount` et `usd_amount` en Decimal/string pour éviter les arrondis float
  - colonnes dérivées : `direction_sign = +1 pour BUY / -1 pour SELL`, `market_age_days`

**3.2 Lien vers les métadonnées de marché**

- `markets.csv` est très large (colonnes en JSON). Extraire dans `processed/markets_flat.parquet` uniquement les champs utiles à l’analyse :
  - `condition_id`, `question`, `slug`, `closed`, `end_date`, `volume_num`, `liquidity_num`, `tags[]`
- Joindre cette table aux trades pour enrichir les analyses

**3.3 Petites tables auxiliaires**

- `processed/users.parquet` — dimensions wallets / slug connus (si lien manuel)
- `processed/events_daily.parquet` — agrégation par (date, market_id)

**3.4 Intégration agentique**

Si l’objectif est d’exposer `poly_data` à un assistant :

- Ajouter un point d’entrée `update_utils.query.py` (ou un petit script `scripts/ask_trades.py`) capable de répondre en langage naturel à des requêtes simples (SQL-like) sur `trades.csv` et `markets_flat.parquet`
- Exposer un **mémoire partagée** (fichier JSON ou YAML) contenant les « insights » du jour, lisible par Hermes / un autre agent via un chemin connu (ex : `poly_data/output/insights.json`)

### Phase 4 — Valorisation (1–3 h)

**4.1 Indicateurs « edge »**

Pour chaque market suivi ou wallet ciblé, calculer :
- volume 24h / 7d / 30d
- ratio buy/sell net (pression acheteur / vendeur)
- nombre de makers uniques actifs
- distribution des tailles de trade (petits vs gros ordres)
- (si possible) reconstruction d’un PnL latéral en utilisant le prix moyen de transaction

**4.2 Détection d’événements**

- flagger les pics de volume ( > 2 écart-types sur la fenêtre 30j)
- lister les nouveaux marchés créés dans les dernières 24h
- alerter sur les fermetures imminentes (end_date < 48h, volume encore significatif)

**4.3 Visualisation / reporting**

- `reports/daily_YYYY-MM-DD.html` (généré par un script) avec :
  - top marchés du jour
  - top traders
  - alertes
- Option : un widget local (fichier HTML) ouvrable dans le navigateur par Hermes `open_preview`

### Phase 5 — Durabilité et automatisation (1–2 h)

**5.1 Mises à jour incrémentales**

- Vérifier que `update_chain` + `process_live` peuvent être lancés indépendamment
- Écrire un petit wrapper `scripts/run_pipeline.sh` (ou Makefile) pour les runs quotidiens/hebdo

**5.2 Sécurité et sauvegarde**

- Ne pas commit `data/processed/` : ajouter à `.gitignore` si ce n’est pas le cas
- Versionner un `snapshots/` léger (metadata uniquement, ex `data/snapshots/markets_head.csv`) pour les checksums

**5.3 Documentation vivante**

- Maintenir un court `README_ANALYSIS.md` qui explique comment lancer l’analyse du jour

---

## Livrables attendus par phase

| Phase | Livrable | Temps estimé |
|---|---|---|
| 1 | `STATUS.md` + pipeline exécuté | 30–60 min |
| 2 | `notebooks/exploration.ipynb` + `analysis/traders.csv` | 1–2 h |
| 3 | `processed/markets_flat.parquet` + point d’interrogation agentique | 2–4 h |
| 4 | `reports/daily_YYYY-MM-DD.html` + indicateurs | 1–3 h |
| 5 | Wrapper + `.gitignore` propre + doc | 1–2 h |

---

## Points de vigilance

- **Volume de données** : `orderFilled.csv` peut vite devenir très gros. Toujours utiliser `polars` en lazy scan, jamais charger tout en mémoire sans `CHUNK_SIZE`.
- **Token HyperSync** : le free tier est très lent pour le backfill initial. Si tu veux accélérer, consider un token payant ou cibler un range de block plus récent (ex : Poly v2 genesis 84 902 353).
- **Qualité des marchés** : beaucoup de conditions sont des « joke markets » ou inchangées depuis des mois. Filtre par `volume_num` et `closed` avant d’analyser.
- **Polars version** : le projet impose `polars>=0.19.0`. Certaines APIs (`.unique(subset=...)`) ont changé au fil des versions — rester cohérent avec le lock file.

---

## Si tu veux que je commence tout de suite

1. Je vérifie l’installation et je lance un run de test (peut-être long)
2. Je te livre un `exploration.ipynb` skeleton prêt à remplir
3. Je produis un Makefile avec les cibles usuelles (`init`, `markets`, `chain`, `process`, `analyze`, `report`)

Dis-moi quelle phase tu veux attaquer en premier.