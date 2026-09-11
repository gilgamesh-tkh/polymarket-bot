"""Génération du contenu markdown des 4 onglets du dashboard.

Chaque fonction prend un `Loader` (dashboard.data) et renvoie un document
markdown autonome, affiché dans un `Markdown` Textual. Toutes sont tolérantes
aux fichiers manquants : les blocs concernés affichent « non disponible ».
"""
from __future__ import annotations

import statistics

from .data import Loader, histogram, quantiles

# --------------------------------------------------------------------- helpers
_PNLC_EDGES = [-1e12, -1000.0, -250.0, -50.0, 0.0, 50.0, 250.0, 1000.0, 1e12]
_PNLC_LABELS = [
    "≤ −1 000 $", "−1 000…−250 $", "−250…−50 $", "−50…0 $",
    "0…50 $", "50…250 $", "250…1 000 $", "> 1 000 $",
]
_ROIC_EDGES = [-1e9, -1.0, -0.5, -0.2, 0.0, 0.2, 0.5, 1.0, 1e9]
_ROIC_LABELS = [
    "≤ −100 %", "−100…−50 %", "−50…−20 %", "−20…0 %",
    "0…20 %", "20…50 %", "50…100 %", "> 100 %",
]
_WRC_EDGES = [0.0, 0.25, 0.5, 0.65, 0.8, 1.001]
_WRC_LABELS = ["0…25 %", "25…50 %", "50…65 %", "65…80 %", "80…100 %"]


def _frnum(x: float, nd: int = 0) -> str:
    """Nombre en format français (1 234 567,89)."""
    s = f"{x:,.{nd}f}"
    if nd:
        ip, dp = s.split(".")
        return ip.replace(",", " ") + "," + dp
    return s.replace(",", " ")


def _pct(x: float, nd: int = 1) -> str:
    return (f"{x:.{nd}f}").replace(".", ",") + " %"


def _dec(x: float, nd: int = 3) -> str:
    """Décimales à la française (0,934)."""
    return f"{x:.{nd}f}".replace(".", ",")


def _usd(x: float, nd: int = 0) -> str:
    return _frnum(x, nd) + " $"


def _bigusd(x: float, nd: int = 1) -> str:
    """Montant avec suffixe G$/M$/k$ (64,6 G$)."""
    sgn = "−" if x < 0 else ""
    a = abs(x)
    if a >= 1e9:
        return f"{sgn}{_dec(a / 1e9, nd)} G$"
    if a >= 1e6:
        return f"{sgn}{_dec(a / 1e6, nd)} M$"
    if a >= 1e3:
        return f"{sgn}{_dec(a / 1e3, nd)} k$"
    return f"{sgn}{_dec(a, nd)} $"


def _dyn_bar(items: list[tuple[str, int, int]], width: int = 26) -> str:
    """Bloc `code` avec barres '█' proportionnelles au max des comptes."""
    mx = max((c for _, c, _ in items), default=1)
    lines = ["```"]
    for label, c, tot in items:
        n_bar = round(c / mx * width)
        share = (100.0 * c / tot) if tot else 0.0
        lines.append(f"{label:<14} {'█' * n_bar:<{width}} {_frnum(c):>7}  {_pct(share)}")
    lines.append("```")
    return "\n".join(lines)


def _avg(series) -> float:
    vals = series.drop_nulls().to_list()
    return statistics.fmean(vals) if vals else float("nan")


def _dist_col(series, edges: list[float], labels: list[str]) -> list[tuple[str, int, int]]:
    counts = histogram(series, edges)
    total = sum(counts)
    return [(lab, c, total) for lab, c in zip(labels, counts)]


def _quant_table(series, cols_labels: list[tuple[str, str]]) -> str:
    """Table markdown des quantiles P5/P25/P50/moyenne/P75/P95 pour plusieurs colonnes."""
    head = "| Variable | P5 | P25 | Médiane | Moyenne | P75 | P95 |"
    sep = "|---|---|---|---|---|---|---|"
    rows = [head, sep]
    for name, col in cols_labels:
        s = series.select(col).to_series()
        q = quantiles(s)
        rows.append(
            f"| {name} | {_fmt_q(q[0], name)} | {_fmt_q(q[1], name)} | "
            f"{_fmt_q(q[2], name)} | {_fmt_q(_avg(s), name)} | "
            f"{_fmt_q(q[3], name)} | {_fmt_q(q[4], name)} |"
        )
    return "\n".join(rows)


def _fmt_q(v: float, col: str) -> str:
    if v != v:  # NaN
        return "—"
    if col == "PnL ($)":
        return _usd(v)
    return _pct(v * 100.0)


# ====================================================================== Onglet 1
def overview_md(d: Loader) -> str:
    out: list[str] = ["# Synthèse des étapes — Pipeline Smart Money", ""]

    # --- Données
    out += ["## Jeu de données", ""]
    qc_q, qc_u, qc_m = d.json("qc_quant"), d.json("qc_users"), d.json("qc_markets")
    if qc_q and qc_u and qc_m:
        out += [
            "| Fichier (parquet) | Lignes |",
            "|---|---:|",
            f"| `markets` | {_frnum(qc_m['num_rows'])} |",
            f"| `quant` | {_frnum(qc_q['meta']['num_rows'])} |",
            f"| `users` | {_frnum(qc_u['meta']['num_rows'])} |",
            "",
            "> Contrôle qualité : 1 331 jours couverts sans trou, doublons ≈ 0 (échantillon 1 %) ; "
            "> 23 lignes `users` à `price > 1` (dust taker/SELL) exclues du PnL.",
            "",
        ]
    else:
        out += ["> ⚠ Résumés QC indisponibles.", ""]

    # --- Résultats clés
    out += ["## Résultats clés", ""]
    pv2, sv2, wfg, wfv2 = (
        d.json("pnl_v2_summary"), d.json("supervised_v2_metrics"),
        d.json("walkforward_grid"), d.json("walkforward_v2_metrics"),
    )
    if pv2:
        out.append(
            f"- **PnL v2 (FIFO)** : ROI médian {_pct(pv2['median_roi'] * 100)}, "
            f"{_pct(pv2['pct_pos_pnl'])} de wallets positifs ; "
            f"seuils H1 : ROI>20 % {_pct(pv2['pct_roi_gt20'])}, WR>65 % {_pct(pv2['pct_winrate_gt65'])}."
        )
    if sv2:
        out.append(
            f"- **Discrimination (48 features)** : XGB AUC-ROC {_dec(sv2['xgb']['auc_mean'])} "
            f"(AUC-PR {_dec(sv2['xgb']['pr_mean'])}) vs RandomForest {_dec(sv2['rf']['auc_mean'])}."
        )
    if wfv2 and "combine (22)" in wfv2:
        v = wfv2["combine (22)"]
        out.append(
            f"- **Prédictif walk-forward** (features enrichies, 22) : AUC-ROC {_dec(v['auc'])} "
            f"(n={_frnum(v['n'])}, {v['n_pos']} positifs futurs) — vs 0,934 en discrimination."
        )
    if wfg:
        expanding = wfg.get("expanding", {})
        aucs = [float(x["auc"]) for x in expanding.values() if x.get("auc") is not None]
        if aucs:
            out.append(
                f"- **Robustesse** (4 coupures) : AUC-ROC {_dec(statistics.fmean(aucs))} en moyenne "
                f"({_dec(min(aucs), 2)}–{_dec(max(aucs), 2)}) ; la purge d'identité révèle une fuite "
                f"(séquentiel 0,85–0,91 → 0,58–0,75)."
            )
    h2 = d.report("h2_report")
    if h2:
        out.append("- **H2 wash trading** : quasi aucun auto-échange (2), réciprocité ~4,8 % des paires / 40,8 % du volume.")
    h3 = d.report("h3_report")
    if h3:
        out.append("- **H3 anomalies volume → prix** : P(Δ>15 %/24 h) 5,7 % vs 5,4 % → H3 **non soutenue**.")
    out.append("")

    # --- Étapes du journal
    out += ["## Étapes (pipeline/ETAT_AVANCEMENT.md)", "", "| Étape | Statut | Commit |", "|---|---|---|"]
    steps = d.steps
    if steps:
        for st in steps:
            title = st["title"]
            if title.startswith("Journal"):
                continue
            title = title.replace("(fait, partiel)", "").replace("(fait)", "").replace("()", "").strip()
            out.append(f"| {title} | {st['status']} | `{st['commit'] or '—'}` |")
    else:
        out.append("| Journal indisponible | — | — |")
    out.append("")
    return "\n".join(out)


# ====================================================================== Onglet 2
def pnl_md(d: Loader) -> str:
    out: list[str] = ["# PnL & Wallets", ""]

    # --- Population / échantillonnage
    out += ["## Population & échantillonnage", ""]
    wincl, wsamp, wt = d.json("wincl_summary"), d.json("wsample_summary"), d.json("wtable_summary")
    if wincl:
        out.append(
            f"- Population brute : **{_frnum(wincl['population_wallets'])} wallets** — "
            f"éligibles : **{_frnum(wincl['eligible_wallets'])} ({_pct(wincl['pct_eligible'], 2)})** "
            f"— volume cumulé {_bigusd(wincl['usd_gross_total'])}."
        )
    if wsamp:
        out += ["", "| Strate (usd_gross) | Alloués |", "|---|---:|"]
        for row in wsamp.get("repartition", []):
            out.append(f"| {row['stratum']} | {_frnum(row['n_sample'])} |")
        out.append(f"| **Total** | **{_frnum(wsamp.get('n_sample_effectif', 0))}** |")
        out.append("")
    if wt:
        out.append(
            f"- Table wallet finale : **{_frnum(wt['n_wallets_table'])} wallets × "
            f"{len(wt['cols'])} features** ; cohérence `usd_gross` recalculé vs primitives = 1,0 (100 %)."
        )
    if not (wincl or wsamp or wt):
        out.append("> ⚠ Résumés population/échantillon indisponibles.")
    out.append("")

    # --- PnL v1 vs v2
    v1, v2 = d.json("pnl_summary"), d.json("pnl_v2_summary")
    out += ["## PnL — v1 (mark-to-market) vs v2 (FIFO corrigé)", ""]
    if v1 and v2:
        out += [
            "| Mesure | v1 m2m | v2 FIFO |",
            "|---|---|---|",
            f"| Wallets analysés | {_frnum(v1['n_wallets'])} | {_frnum(v2['n_wallets'])} |",
            f"| PnL > 0 | {_pct(v1['pct_pos_m2m'])} | {_pct(v2['pct_pos_pnl'])} |",
            f"| PnL médian | {_usd(v1['median_pnl_m2m'])} | {_usd(v2['median_pnl'])} |",
            f"| ROI médian | {_pct(v1['median_roi_m2m'] * 100)} | {_pct(v2['median_roi'] * 100)} |",
            f"| Win rate médian | {_pct(v1['median_win_rate'] * 100)} | {_pct(v2['median_win_rate'] * 100)} |",
            f"| ROI > 20 % | {_pct(v1['pct_roi_gt20'])} | {_pct(v2['pct_roi_gt20'])} |",
            f"| WR > 65 % | {_pct(v1['pct_winrate_gt65'])} | {_pct(v2['pct_winrate_gt65'])} |",
            "",
            "> La v2 attribue les ventes en **FIFO temporel** : les ventes de tokens *jamais achetés "
            "dans la fenêtre* (market makers / mint) ne sont plus créditées comme profit fictif "
            "(112 239 paires en déficit, 1,8 % → correction FIFO stricte ; 387 wallets |Δ|>100 $).",
            "",
        ]
    else:
        out.append("> ⚠ Résumés PnL v1/v2 indisponibles.")
        out.append("")

    # --- Live
    df = d.pnl_wallet
    out += ["## Distributions live (`wallet_pnl_wallet_v2.parquet`)", ""]
    if df is not None:
        n = df.height
        out.append(f"Source : **{_frnum(n)} wallets** — quantiles recalculés à la volée.")
        out.append("")
        out.append(_quant_table(df, [("PnL ($)", "pnl"), ("ROI (%)", "roi"), ("Win rate (%)", "win_rate_m2m")]))
        out.append("")
        pos_pnl = df.filter(df["pnl"] > 0).height
        roi20 = df.filter(df["roi"] > 0.20).height
        wr65 = df.filter(df["win_rate_m2m"] > 0.65).height
        n_pnl = df["pnl"].drop_nulls().len()
        n_roi = df["roi"].drop_nulls().len()
        n_wr = df["win_rate_m2m"].drop_nulls().len()
        out.append(
            f"- Wallets **PnL > 0** : {_frnum(pos_pnl)} ({_pct(100 * pos_pnl / n_pnl)}) | "
            f"**ROI > 20 %** : {_frnum(roi20)} ({_pct(100 * roi20 / n_roi)}) | "
            f"**Win rate > 65 %** : {_frnum(wr65)} ({_pct(100 * wr65 / n_wr)})"
        )
        out.append("")
        out.append("_Les parts sous les barres portent sur les wallets non nuls de la variable "
                   "(win rate absent si aucun marché résolu)._")
        out.append("")
        out.append("### PnL (par wallet)")
        out.append(_dyn_bar(_dist_col(df["pnl"], _PNLC_EDGES, _PNLC_LABELS)))
        out.append("")
        out.append("### ROI (PnL / coût)")
        out.append(_dyn_bar(_dist_col(df["roi"], _ROIC_EDGES, _ROIC_LABELS)))
        out.append("")
        out.append("### Win rate (marchés résolus)")
        out.append(_dyn_bar(_dist_col(df["win_rate_m2m"], _WRC_EDGES, _WRC_LABELS)))
    else:
        out.append("> ⚠ Parquet `wallet_pnl_wallet_v2.parquet` indisponible.")
    out.append("")
    return "\n".join(out)


# ====================================================================== Onglet 3
def models_md(d: Loader) -> str:
    out: list[str] = ["# Modèles — label Smart Money (H1)", ""]
    s7, s7e = d.json("supervised_metrics"), d.json("supervised_v2_metrics")

    # --- Discrimination
    out += ["## Discrimination (features & label contemporains)", ""]
    if s7 and s7e:
        out += [
            "| Étape | Features | AUC-ROC RF | AUC-ROC XGB | AUC-PR XGB |",
            "|---|---|---|---|---|",
            f"| 7 (base) | {len(s7['features'])} | {_dec(s7['rf']['auc_mean'])} | "
            f"{_dec(s7['xgb']['auc_mean'])} | {_dec(s7['xgb']['pr_mean'])} |",
            f"| 7e (final, X1-X4) | {s7e['n_feats']} | {_dec(s7e['rf']['auc_mean'])} | "
            f"{_dec(s7e['xgb']['auc_mean'])} | {_dec(s7e['xgb']['pr_mean'])} |",
            "",
            "> Intermédiaires (journal) : 7c +8 features avancées → AUC 0,919 / 0,913 ; "
            "7d features A+B+C (41) → 0,938 / 0,928. Population : "
            f"**{_frnum(s7e['n'])} wallets, {_frnum(s7e['n_pos'])} positifs H1 "
            f"({_pct(100 * s7e['n_pos'] / s7e['n'])})**.",
            "",
        ]
    else:
        out.append("> ⚠ Résumés supervisés indisponibles.")
        out.append("")

    # --- Importances
    if s7e and s7e.get("importances"):
        out += ["### Top features (XGBoost, 48 features)", "", "| # | Feature | Importance |", "|---|---|---:|"]
        for i, imp in enumerate(s7e["importances"][:10], start=1):
            out.append(f"| {i} | `{imp['feature']}` | {_dec(imp['xgb'])} |")
        out.append("")

    # --- Walk-forward
    out += ["## Walk-forward prédictif (features passées → label futur)", ""]
    wfv2 = d.json("walkforward_v2_metrics")
    if wfv2:
        out += ["| Features | AUC-ROC | AUC-PR | F1 max | n | positifs |", "|---|---|---|---|---|---|"]
        for key, v in wfv2.items():
            out.append(
                f"| {key} | {_dec(v['auc'])} | {_dec(v['pr'])} | {_dec(v['best_f1'])} | "
                f"{_frnum(v['n'])} | {v['n_pos']} |"
            )
        out.append("")
    wf = d.json("walkforward_metrics")
    if wf:
        out.append(
            f"- Première coupure 2025-06-30 (12 features) : RF {_dec(wf['rf']['auc'], 2)} / "
            f"XGB {_dec(wf['xgb']['auc'], 2)} — n={_frnum(wf['rf']['n'])}, {wf['rf']['n_pos']} positifs."
        )
    wfg = d.json("walkforward_grid")
    if wfg and wfg.get("expanding"):
        out += ["", "### Grille multi-coupures (expansion, purgée)", "", "| Coupure | n | positifs | AUC-ROC | AUC-PR |", "|---|---|---|---|---|"]
        for cut, v in wfg["expanding"].items():
            out.append(f"| {cut} | {_frnum(v['n'])} | {v['n_pos']} | {_dec(v['auc'])} | {_dec(v['pr'])} |")
        out.append("")
    if wfg and wfg.get("sequential"):
        out += ["", "### Séquentiel strict — purge d'identité", "", "| train → test | n_train | n_test | AUC-ROC | AUC-PR |", "|---|---|---|---|---|"]
        for r in wfg["sequential"]:
            out.append(
                f"| {r['train_cut']} → {r['test_cut']} | {_frnum(r['n_train'])} | "
                f"{_frnum(r['n_test'])} | {_dec(r['auc'])} | {_dec(r['pr'])} |"
            )
        out += [
            "",
            "> ⚠ La comparaison séquentiel *sans* purge (0,85–0,91) vs *avec* purge (0,58–0,75) "
            "mesure la **fuite d'identité** : un même wallet en train et en test gonfle "
            "massivement l'AUC (voir journal, étape 8c).",
        ]
    out.append("")
    return "\n".join(out)


# ====================================================================== Onglet 4
def hypotheses_md(d: Loader) -> str:
    out: list[str] = ["# Hypothèses H1 / H2 / H3", ""]

    # H1
    ca = d.json("cluster_analysis")
    out += ["## H1 — la Smart Money est détectable", ""]
    if ca:
        out.append(
            f"- Label (a posteriori) : ROI > 20 % **et** WR > 65 % sur marchés résolus → "
            f"**{_frnum(ca['n_h1'])} wallets sur {_frnum(ca['n_wallets'])} "
            f"({_pct(100 * ca['n_h1'] / ca['n_wallets'])})**."
        )
    out.append(
        "- Clustering (K-Means, k optimal=3) : silhouette faible → continuum d'activité, "
        "sépare la **taille** pas la performance ; lift max 2,8× → le clustering seul n'isole pas la SM."
    )
    out.append(
        "- Classifieur supervisé : **discrimine** bien (AUC 0,93) mais la partie *prédictive* "
        "réelle est modeste (walk-forward AUC ≈ 0,74) — le reste vient de la contemporanéité."
    )
    out.append("")

    # H2
    h2 = d.report("h2_report")
    out += ["## H2 — wash trading (auto-échanges & paires réciproques)", ""]
    if h2:
        out.append(
            "- **Auto-échanges quasi inexistants** (2 self-trades sur 43,3 M legs) → pas de wash "
            "par auto-échange."
        )
        out.append(
            "- Paires réciproques : 4,8 % des paires mais **40,8 % du volume** (dont MM légitimes)."
        )
        out.append(
            "- Wash *suspect* (réciproque + ≥10 k$ + ≥20 trades) : 5 058 paires, **9,1 % du volume** ; "
            "seulement 4/99 wallets H1 impliqués."
        )
        out.append("")
        out.append("### Verdict : H2 **partiellement soutenue** — wash direct inexistant, proxy "
                   "réciprocité ~5–9 % (limites documentées dans le rapport).")
        out.append("")
    out.append("")

    # H3
    h3 = d.report("h3_report")
    out += ["## H3 — anomalies de volume → mouvements de prix (longshots)", ""]
    if h3:
        out.append(
            "- Longshots faible liquidité : 117 705 marchés ; P(Δprix>15 % en 24 h) "
            "**5,7 %** (anomalie) vs **5,4 %** (baseline), p<10⁻⁸ mais effet faible ; médiane |Δ| "
            "double (0,011 → 0,020)."
        )
        out.append("")
        out.append("### Verdict : H3 **non soutenue** — le volume suit le prix plus qu'il ne le précède.")
        out.append("")
    else:
        out.append("> ⚠ Rapports H2/H3 indisponibles.")

    out += ["", "---", "", "### Rapports détaillés (extraits)", ""]
    for stem, label in [("h2_report", "H2 — wash trading"), ("h3_report", "H3 — anomalies volume")]:
        txt = d.report(stem)
        if txt:
            out.append(f"**{label}**  ")
            out.append("")
            out.append(txt)
            out.append("")
    return "\n".join(out)
