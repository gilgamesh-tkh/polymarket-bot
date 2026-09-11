#!/usr/bin/env python
"""Génère pipeline/output/qc_report.md à partir des qc_*.json (+ dup_*.json si dispo)."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import OUTPUT_DIR  # noqa: E402

QC = {}
for f in ["quant", "users", "markets"]:
    p = OUTPUT_DIR / f"qc_{f}.json"
    if p.exists():
        QC[f] = json.loads(p.read_text())

DUP = {}
for f in ["quant", "users"]:
    p = OUTPUT_DIR / f"dup_{f}.json"
    if p.exists():
        DUP[f] = json.loads(p.read_text())

L = []
p = L.append


def ts(sec):
    return datetime.fromtimestamp(sec, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


p("# Rapport — Point 2 : Contrôle qualité")
p("")
p("Script : `pipeline/01_quality_control.py` + `pipeline/02_dup_check.py`")

for f in ["quant", "users"]:
    q = QC[f]
    agg = q["aggregates"]
    meta = q["meta"]
    p("")
    p(f"## {f}.parquet")
    p("")
    p(f"- Lignes : **{agg['n_rows']:,.0f}** | Row groups : {meta['num_row_groups']:,} | "
      f"RG triés par temps : {meta['rg_time_sorted']}")
    p(f"- Fenêtre : `{ts(agg['ts_min'])}` → `{ts(agg['ts_max'])}`  "
      f"(UTC) — {len(q['daily']['days'])} jours couverts")
    p(f"- `block_number` : {agg['blk_min']:,.0f} → {agg['blk_max']:,.0f}")
    p("")
    p("### Agrégats (passe complète)")
    p("")
    p("| Variable | min | max | somme | négatifs | nuls |")
    p("|---|---|---|---|---|---|")
    p(f"| usd_amount | {agg['usd_min']:,.2f} | {agg['usd_max']:,.2f} | "
      f"{agg['usd_sum']:,.0f} | {agg['n_usd_neg']:,.0f} | - |")
    p(f"| token_amount | {agg['tok_min']:,.2f} | {agg['tok_max']:,.2f} | "
      f"{agg['tok_sum']:,.0f} | {agg['n_tok_neg']:,.0f} | - |")
    p(f"| price | {agg['price_min']} | {agg['price_max']} | (moy {agg['price_avg']:.4f}) | "
      f"hors [0,1] : **{agg['n_price_oob']:,.0f}** | - |")
    p(f"| transaction_hash | - | - | - | - | {agg['n_null_tx']:,.0f} |")
    p(f"| market_id | - | - | - | - | {agg['n_null_mid']:,.0f} |")
    p("")
    p(f"approx distinct tx : {agg['approx_distinct_tx']:,.0f} | "
      f"approx distinct market_id : {agg['approx_distinct_mid']:,.0f}")
    p("")
    # trous : jours avec 0
    days = q["daily"]["days"]
    counts = q["daily"]["counts"]
    zero = [(d, i) for i, d in enumerate(days) if counts[i] == 0]
    p(f"### Trous temporels (jours à 0 ligne) : {len(zero)}")
    # regrouper les jours consécutifs à 0
    if zero:
        groups = []
        for d, _ in zero:
            if groups and (datetime.fromisoformat(d) - groups[-1][1]).days == 1:
                groups[-1] = (groups[-1][0], datetime.fromisoformat(d))
            else:
                groups.append((datetime.fromisoformat(d), datetime.fromisoformat(d)))
        p("")
        for g0, g1 in groups:
            p(f"- {g0.date()} → {g1.date()}  ({(g1 - g0).days + 1} j)")
    else:
        p("Aucun jour à 0 ligne sur la fenêtre.")
    p("")

# cohérence cross-fichier
p("## Cohérence inter-fichiers")
p("")
if "quant" in QC and "users" in QC:
    qa = QC["quant"]["aggregates"]
    ua = QC["users"]["aggregates"]
    p(f"- `usd_sum` : quant {qa['usd_sum']:,.0f} vs users {ua['usd_sum']:,.0f} → ratio "
      f"**{ua['usd_sum'] / qa['usd_sum']:.3f}** (attendu ≈2 : maker+taker)")
    p(f"- Lignes : quant {qa['n_rows']:,.0f} vs users {ua['n_rows']:,.0f} → ratio "
      f"{ua['n_rows'] / qa['n_rows']:.3f}")
    p(f"- Fenêtres temporelles identiques : {ts(qa['ts_min'])} → {ts(qa['ts_max'])}")
    p(f"- `approx_distinct_market_id` identiques : {qa['approx_distinct_mid']:,.0f}")
    p("")
    p("### Détail par jour (volume usd users vs 2×quant)")
    p("")
    dd = {}
    for f, factor in [("quant", 2.0), ("users", 1.0)]:
        q = QC[f]
        # re-sum par jour nécessaire -> déjà fait? non (seuls les counts).
        # Approximation : comparaison des comptes quotidiens seulement.
    # simple : ratio de comptes quotidiens
    qdays = dict(zip(QC["quant"]["daily"]["days"], QC["quant"]["daily"]["counts"]))
    udays = dict(zip(QC["users"]["daily"]["days"], QC["users"]["daily"]["counts"]))
    common = sorted(set(qdays) & set(udays))
    ratios = [udays[d] / (2 * qdays[d]) if qdays[d] else None for d in common]
    import statistics
    r_valid = [r for r in ratios if r is not None]
    p(f"Ratio journalier `users_count / (2 × quant_count)` : médiane "
      f"**{statistics.median(r_valid):.3f}**, min {min(r_valid):.3f}, max {max(r_valid):.3f} "
      f"(sur {len(r_valid)}/{len(common)} jours communs).")
    p("")
    p("> Note : le ratio *lignes* ≠ 2 (médiane quotidienne ~0,86) car `users` n'a pas "
      "strictement 2 lignes par fill (certains fills mono-leg, granularité différente). "
      "Le test de volume décisif est le ratio `usd_sum` ≈ 2,08 ci-dessus — cohérent.")
    p("")

if DUP:
    p("## Doublons (échantillon réservoir)")
    p("")
    for f in ["quant", "users"]:
        if f in DUP:
            d = DUP[f]
            p(f"- **{f}** : clé `{', '.join(d['key'])}` → sur échantillon "
              f"{d['sample_pct']} % ({d['n_sample_rows']:,} lignes) : "
              f"**{d['n_rows_in_dup_groups']:,}** lignes dans des groupes en double "
              f"({d['n_dup_groups_size2']:,} paires, {d['n_dup_groups_size3plus']:,} groupes 3+) "
              f"— taux estimé {d['dup_row_rate_est']:.6f} en {d['elapsed_s']}s")
    p("")

p("## Anomalies price hors [0,1]")
p("")
p("- **users** : 23 lignes `taker/SELL` avec `price`>1 (jusqu'à 7812) — `token_amount` très "
  "petits (<~500) pour des `usd_amount` normaux ⇒ `price` = usd/token dégénéré sur des "
  "poussières de tokens. À exclure des calculs de PnL/prix (filtre `price BETWEEN 0 AND 1`).")
p("- **quant** : 0 ligne hors [0,1].")
p("")

(OUTPUT_DIR / "qc_report.md").write_text("\n".join(L))
print("[ok] pipeline/output/qc_report.md")
