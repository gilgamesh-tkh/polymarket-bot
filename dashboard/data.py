"""Chargement des résultats du pipeline Smart Money pour le dashboard TUI.

Lecture volontairement **légère** (aucun scan des gros fichiers quant/users) :
  * résumés JSON `pipeline/output/*_summary.json`, `*_metrics.json`,
    `*_analysis.json` produits à chaque étape ;
  * rapports markdown `pipeline/output/*_report.md` et journal
    `pipeline/ETAT_AVANCEMENT.md` ;
  * stats « live » recalculées à la volée sur les parquet wallet-level légers
    (`wallet_pnl_wallet_v2.parquet`, ~10 k lignes) et la table wallet
    (`wallet_table.parquet`, ~10 k lignes × 31 colonnes).

Chaque méthode est tolérante : si un fichier manque, elle renvoie `None`/`""`
et la vue affiche « non disponible » au lieu de planter.
"""
from __future__ import annotations

import json
import re
from functools import cached_property
from pathlib import Path

import polars as pl

REPO = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO / "pipeline" / "output"
ETAT_PATH = REPO / "pipeline" / "ETAT_AVANCEMENT.md"

# Colonnes pertinentes des parquet wallet-level pour le calcul live.
PNL_COLS = ["pnl", "roi", "win_rate_m2m"]

_STEP_RE = re.compile(r"^\s*Commit\s*:\s*`([0-9a-fA-F]{7,})`")
_STATUS_RE = re.compile(r"\((?P<status>fait|partiel|en cours|à faire)[^)]*\)")


class Loader:
    """Point d'accès unique aux résultats du pipeline (résumés + rapports + parquet live)."""

    def __init__(self, output_dir: Path | str = OUTPUT_DIR, etat_path: Path | str = ETAT_PATH):
        self.output_dir = Path(output_dir)
        self.etat_path = Path(etat_path)

    # ------------------------------------------------------------------ JSON
    def json(self, stem: str) -> dict | None:
        """Lit `pipeline/output/<stem>.json` en dict (None si absent/invalide)."""
        path = self.output_dir / f"{stem}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    # ------------------------------------------------------------- rapports
    def report(self, stem: str) -> str:
        """Contenu markdown brut de `pipeline/output/<stem>.md` ('' si absent)."""
        path = self.output_dir / f"{stem}.md"
        if not path.exists():
            return ""
        try:
            return path.read_text().strip()
        except OSError:
            return ""

    # --------------------------------------------------------------- journal
    def etat_text(self) -> str:
        """Texte brut du journal pipeline/ETAT_AVANCEMENT.md ('' si absent)."""
        if not self.etat_path.exists():
            return ""
        try:
            return self.etat_path.read_text()
        except OSError:
            return ""

    @cached_property
    def steps(self) -> list[dict]:
        """Sections `## Étape …` du journal, dans l'ordre du document."""
        text = self.etat_text()
        if not text:
            return []
        steps: list[dict] = []
        cur: dict | None = None
        for raw in text.splitlines():
            if raw.startswith("## "):
                if cur is not None:
                    steps.append(cur)
                title = raw[3:].strip()
                status = "—"
                m = _STATUS_RE.search(title)
                if m:
                    status = m.group("status")
                cur = {"title": title, "status": status, "commit": None, "body": []}
            elif cur is not None and cur["commit"] is None:
                m = _STEP_RE.search(raw)
                if m:
                    cur["commit"] = m.group(1)
        if cur is not None:
            steps.append(cur)
        return steps

    # --------------------------------------------------------- parquet live
    def parquet(self, stem: str) -> pl.DataFrame | None:
        """Charge un parquet du répertoire de sortie (None si absent)."""
        path = self.output_dir / f"{stem}.parquet"
        if not path.exists():
            return None
        try:
            return pl.read_parquet(path)
        except Exception:
            return None

    @cached_property
    def pnl_wallet(self) -> pl.DataFrame | None:
        """PnL v2 wallet-level (9 855 lignes) — source des stats live PnL."""
        return self.parquet("wallet_pnl_wallet_v2")

    @cached_property
    def wallet_table(self) -> pl.DataFrame | None:
        """Table wallet X1–X3 (10 000 × 31) — pour infos de structure."""
        return self.parquet("wallet_table")


# ====================================================================== utils
def quantiles(series: pl.Series, probs: tuple[float, ...] = (0.05, 0.25, 0.5, 0.75, 0.95)) -> list[float]:
    """Quantiles d'une série polars (les nulls sont ignorés)."""
    s = series.drop_nulls()
    if s.len() == 0:
        return [float("nan")] * len(probs)
    return [s.quantile(p) for p in probs]


def histogram(series: pl.Series, edges: list[float]) -> list[int]:
    """Compte par bins délimités par `edges` (bornes incluses à gauche)."""
    s = series.drop_nulls().to_list()
    counts = [0] * (len(edges) - 1)
    for v in s:
        for i in range(len(edges) - 1):
            lo, hi = edges[i], edges[i + 1]
            if lo <= v < hi:
                counts[i] += 1
                break
    return counts
