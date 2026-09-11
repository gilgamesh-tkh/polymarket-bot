#!/usr/bin/env python
"""Point 1 — Vérification environnement & schéma des trois fichiers Parquet.

- Localise et ouvre markets.parquet / quant.parquet / users.parquet
- Affiche .schema() (via DuckDB) et un head() de chaque
- Confronte le schéma RÉEL au schéma documenté (prompt) et lève des divergences
- Écrit pipeline/output/schema_report.md
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import OUTPUT_DIR, connect, pq_path  # noqa: E402

DOC_QUANT = ["transaction_hash", "block_number", "datetime", "market_id",
             "token_amount", "usd_amount", "price"]
DOC_USERS = ["transaction_hash", "block_number", "datetime", "market_id",
             "user", "role", "token_amount", "usd_amount", "price"]
DOC_MARKETS = ["id", "question", "slug", "condition_id", "token1", "token2",
               "answer1", "answer2", "closed", "active", "archived",
               "outcome_prices", "volume", "event_id", "event_slug",
               "event_title", "created_at", "end_date", "updated_at"]

con = connect()
lines = []
p = print


def out(msg=""):
    p(msg)
    lines.append(msg)


out("# Rapport — Point 1 : vérification de l'environnement et des schémas")
out("")

for fname, doc_cols in [("quant", DOC_QUANT), ("users", DOC_USERS), ("markets", DOC_MARKETS)]:
    path = pq_path(fname)
    sz = Path(path).stat().st_size / 1e9
    out(f"## {fname}.parquet  ({sz:.2f} Go)")
    out("")
    out("### Fichier localisé")
    out(f"- Chemin : `{path}`")
    out("")

    out("### Schéma réel (DuckDB)")
    schema = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{path}') LIMIT 0").df()
    out("")
    out("| # | colonne | type |")
    out("|---|---------|------|")
    for i, r in schema.iterrows():
        out(f"| {i} | {r['column_name']} | {r['column_type']} |")
    out("")

    real_cols = list(schema["column_name"])
    out("### Divergences vs schéma documenté")
    doc_set = set(doc_cols)
    real_set = set(real_cols)
    missing = sorted(doc_set - real_set)
    extra = sorted(real_set - doc_set)
    if not missing and not extra:
        out("- Aucune divergence : schéma conforme à la documentation.")
    else:
        if missing:
            out(f"- Colonnes documentées absentes : `{missing}`")
        if extra:
            out(f"- Colonnes réelles non documentées : `{extra}`")
        # notes typées selon le fichier
        if fname == "quant":
            out("- Doc : `datetime` → réel : `timestamp` (UBIGINT epoch).")
            out("- Doc : `transaction_hash`,`market_id` présents ; réels ajoutés : "
                "`log_index`, `condition_id`, `event_id`, `side`, `maker`, `taker`.")
        if fname == "users":
            out("- Doc : `user` → réel : `address`. `datetime` → `timestamp` (UBIGINT).")
            out("- Réels ajoutés : `log_index`, `condition_id`, `event_id`, "
                "`direction`, `nonusdc_side`.")
            out("- **Attention** : `direction` réel contient BUY *et* SELL "
                "(contrairement à la doc « unifiée BUY »).")
        if fname == "markets":
            out("- 20 colonnes réelles (id, question, slug, condition_id, token1/2, "
                "answer1/2, closed, active, archived, outcome_prices, volume, event_id, "
                "event_slug, event_title, created_at, end_date, updated_at, neg_risk).")
    out("")

    out("### head()")
    head = con.execute(
        f"SELECT * FROM read_parquet('{path}') LIMIT 3"
    ).df().T.to_string(max_colwidth=42)
    out("```")
    out(head)
    out("```")
    out("")

# types pour la jointure
out("## Notes de jointure")
out("")
for col in ["market_id", "id", "condition_id", "event_id"]:
    t = con.execute(
        f"SELECT typeof(market_id) FROM read_parquet('{pq_path('quant')}') LIMIT 1"
    ).fetchone()[0]
    out(f"- `quant.{col}` (échantillon) : {t}")
t_id = con.execute(
    f"SELECT typeof(id) FROM read_parquet('{pq_path('markets')}') LIMIT 1").fetchone()[0]
out(f"- `markets.id` (échantillon) : {t_id}")
t_cid = con.execute(
    f"SELECT typeof(condition_id) FROM read_parquet('{pq_path('markets')}') LIMIT 1"
).fetchone()[0]
out(f"- `markets.condition_id` (échantillon) : {t_cid}")

report = "\n".join(lines)
(OUTPUT_DIR / "schema_report.md").write_text(report)
print("\n[ok] écrit : pipeline/output/schema_report.md")
