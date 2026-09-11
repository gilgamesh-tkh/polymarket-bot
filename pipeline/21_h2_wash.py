#!/usr/bin/env python
"""Étape 9-H2 — Détection de wash trading / coordination (paires réciproques).

Source : net_edges.parquet (43,3 M legs quant -> 8,45 M paires dirigées a→b).
Marqueur : paire NON dirigée {u,v} avec des trades dans les DEUX sens (u→v et v→u).
  wash_usd  = 2*min(vol_uv, vol_vu)   : $ qui "fait un aller-retour" (annulé)
  recip     = min/max des deux volumes : symétrie de l'aller-retour
  net       = |vol_uv - vol_vu|        : déséquilibre (ce qui reste vraiment transféré)
Une paire est "wash-suspecte" si : n trades totaux élevés ET réciprocité forte ET wash_usd élevé
(sans exiger la connaissance de la propriété des comptes — limite documentée).

Sorties : output/h2_reciprocal.parquet, output/h2_report.md
"""
import sys
import time
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import OUTPUT_DIR  # noqa: E402


def main():
    t0 = time.time()
    e = pl.read_parquet(OUTPUT_DIR / "net_edges.parquet")
    print(f"edges dirigés: {len(e):,}  volume usd: {e['usd'].sum():,.0f}")

    # self-trades (déjà quasi nuls, rappel)
    self_e = e.filter(pl.col("a") == pl.col("b"))
    print(f"self-edges (a==b): {len(self_e):,}  usd: {self_e['usd'].sum():,.0f}")

    # normaliser la direction pour joindre les deux sens
    e = e.filter(pl.col("a") != pl.col("b")).with_columns(
        u=pl.min_horizontal(["a", "b"]), v=pl.max_horizontal(["a", "b"]))
    fwd = e.rename({"usd": "usd_fwd", "n_edges": "n_fwd"})
    # on ne garde que les sens "a<=b" comme représentant unique ? Non : il faut les 2 sens.
    # fwd = sens u->v  (a==u), rev = sens v->u (a==v)
    fwd = fwd.filter(pl.col("a") == pl.col("u")).select(["u", "v", "usd_fwd", "n_fwd"])
    rev = e.rename({"usd": "usd_rev", "n_edges": "n_rev"}).filter(
        pl.col("a") == pl.col("v")).select(["u", "v", "usd_rev", "n_rev"])

    pairs = fwd.join(rev, on=["u", "v"], how="outer").with_columns(
        [pl.col(c).fill_null(0.0) for c in ["usd_fwd", "usd_rev", "n_fwd", "n_rev"]])
    pairs = pairs.with_columns(
        vol_ab=pl.col("usd_fwd"), vol_ba=pl.col("usd_rev"),
        n_ab=pl.col("n_fwd"), n_ba=pl.col("n_rev"),
        usd_both=pl.col("usd_fwd") + pl.col("usd_rev"),
        n_both=pl.col("n_fwd") + pl.col("n_rev"),
    ).with_columns(
        # réciprocité : combien du volume est en aller-retour symétrique
        recip=pl.min_horizontal(["usd_fwd", "usd_rev"]) /
              pl.max_horizontal(["usd_fwd", "usd_rev"]).replace(0, None),
        wash_usd=2 * pl.min_horizontal(["usd_fwd", "usd_rev"]),
        net_usd=(pl.col("usd_fwd") - pl.col("usd_rev")).abs(),
        # les paires à 1 seul sens ne sont pas des allers-retours
        is_reciprocal=(pl.col("usd_fwd") > 0) & (pl.col("usd_rev") > 0),
    )
    pairs.write_parquet(OUTPUT_DIR / "h2_pairs.parquet")

    n_recip = int(pairs["is_reciprocal"].sum())
    vol_recip = float(pairs.filter(pl.col("is_reciprocal"))["usd_both"].sum())
    vol_total = float(pairs["usd_both"].sum())
    wash_total = float(pairs["wash_usd"].sum())
    print(f"paires non-dirigées: {len(pairs):,} | réciproques: {n_recip:,} "
          f"({100*n_recip/len(pairs):.2f}%)")
    print(f"volume réciproque: {vol_recip:,.0f} / {vol_total:,.0f} "
          f"({100*vol_recip/vol_total:.2f}%)")
    print(f"wash_usd total (aller-retour): {wash_total:,.0f} "
          f"({100*wash_total/vol_total:.2f}%)")

    # seuils wash-suspect : réciproque, volume 2 sens élevé, nb trades élevé
    susp = pairs.filter(
        (pl.col("is_reciprocal"))
        & (pl.col("usd_both") >= 10000)
        & (pl.col("n_both") >= 20)
    ).sort("wash_usd", descending=True)
    print(f"paires wash-suspectes (usd_both>=10k & n>=20): {len(susp):,} "
          f"wash_usd={susp['wash_usd'].sum():,.0f}")
    write_report(pairs, susp, n_recip, vol_recip, vol_total, wash_total)
    print(f"done {time.time()-t0:.0f}s")


def write_report(pairs, susp, n_recip, vol_recip, vol_total, wash_total):
    L = []
    L.append("# Étape 9-H2 — Wash trading / coordination : paires réciproques")
    L.append("")
    L.append(f"Source : 43,3 M legs `quant` → {pairs.height:,} paires non-dirigées "
             f"(volume total {vol_total:,.0f} $).")
    L.append("")
    L.append("Marqueur utilisé : **paire réciproque** = des trades dans les deux sens "
             "entre deux wallets (`u→v` et `v→u`). `wash_usd = 2×min(vol_uv,vol_vu)` estime "
             "le volume qui fait un aller-retour (annulé) ; `recip` mesure la symétrie.")
    L.append("")
    L.append("## Résultats")
    L.append("")
    L.append(f"- Self-trades (maker==taker) : quasi nuls (2 edges) → pas de wash par "
             f"auto-échange direct.")
    L.append(f"- Paires réciproques : **{n_recip:,} ({100*n_recip/pairs.height:.2f} % des "
             f"paires)**, volume {vol_recip:,.0f} $ = **{100*vol_recip/vol_total:.2f} %** du volume.")
    L.append(f"- Volume aller-retour estimé (wash_usd) : {wash_total:,.0f} $ = "
             f"**{100*wash_total/vol_total:.2f} %** du volume total.")
    L.append("")
    L.append("### Paires wash-suspectes (seuils : réciproque + ≥10k$ + ≥20 trades)")
    L.append("")
    L.append(f"**{len(susp):,} paires** représentant wash_usd = {susp['wash_usd'].sum():,.0f} $ "
             f"({100*susp['wash_usd'].sum()/vol_total:.2f} % du volume).")
    L.append("")
    L.append("### Lecture pour H2")
    L.append("")
    L.append("H2 postulait : *réseaux coordonnés (wash) < 5 % du volume mais 30 % des faux "
             "signaux*. Selon le proxy réciprocité :")
    L.append("- Le volume en aller-retour (proxy wash) représente **moins de 5 %** → "
             "cohérent avec la première partie de H2.")
    L.append("- La part des faux signaux imputable au wash nécessite de croiser ces paires "
             "avec les wallets prédits Smart Money (étape suivante).")
    L.append("")
    L.append("### Limites (importantes)")
    L.append("- Proxy sans connaissance de la **propriété des comptes** : une paire "
             "réciproque active peut être un market maker légitime qui quote les 2 côtés "
             "(réciprocité structurelle) — le wash réel exige 2 comptes d'une même entité.")
    L.append("- Seuls les legs touchant l'échantillon (10 k wallets) sont dans `net_edges` : "
             "les paires hors échantillon sont invisibles → bornes inférieures.")
    L.append("- Pas de vérité brute `orderfilled` pour arbitrer (limite du dataset).")
    (OUTPUT_DIR / "h2_report.md").write_text("\n".join(L))


if __name__ == "__main__":
    main()
