"""Application Textual : dashboard TUI des résultats du pipeline Smart Money.

Lancement : `python -m dashboard` (venv polyenv).

Onglets (touches 1-4), rechargement des données (r), sortie (q).
"""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Markdown, TabbedContent, TabPane

from .data import Loader
from . import views

VIEWS = [
    ("overview", "1 · Synthèse", views.overview_md),
    ("pnl", "2 · PnL & wallets", views.pnl_md),
    ("models", "3 · Modèles ML", views.models_md),
    ("hyp", "4 · Hypothèses H1/H2/H3", views.hypotheses_md),
]

CSS = """
Screen {
    layout: vertical;
}
Header {
    dock: top;
}
Footer {
    dock: bottom;
}
#tabs {
    height: 1fr;
    padding: 0 1;
}
Markdown {
    height: 1fr;
    border: round $primary 20%;
    padding: 0 2;
    scrollbar-size: 1 1;
}
Markdown:focus {
    border: round $primary;
}
"""


class DashboardApp(App[None]):
    """Affiche les résultats du pipeline Smart Money dans des onglets."""

    TITLE = "Dashboard Smart Money"
    SUB_TITLE = "Pipeline SII-WANGZJ/Polymarket_data — résultats des étapes 0-10"

    BINDINGS = [
        Binding("1", "goto(0)", "Synthèse"),
        Binding("2", "goto(1)", "PnL & wallets"),
        Binding("3", "goto(2)", "Modèles"),
        Binding("4", "goto(3)", "Hypothèses"),
        Binding("r", "reload", "Recharger"),
        Binding("q", "quit", "Quitter"),
    ]

    def __init__(self, loader: Loader | None = None):
        super().__init__()
        self.loader = loader or Loader()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial=VIEWS[0][0]) as tabs:
            tabs.id = "tabs"
            for key, title, _ in VIEWS:
                with TabPane(title, id=key):
                    yield Markdown("", id=f"md-{key}")
        yield Footer()

    def on_mount(self) -> None:
        for key, _, builder in VIEWS:
            self.query_one(f"#md-{key}", Markdown).update(builder(self.loader))

    # ------------------------------------------------------------- actions
    def action_goto(self, idx: int) -> None:
        key = VIEWS[idx][0]
        self.query_one("#tabs", TabbedContent).active = key

    def action_reload(self) -> None:
        """Recharge le contenu de l'onglet actif depuis le disque."""
        tabs = self.query_one("#tabs", TabbedContent)
        key = tabs.active or VIEWS[0][0]
        if key not in {k for k, _, _ in VIEWS}:
            key = VIEWS[0][0]
        md = self.query_one(f"#md-{key}", Markdown)
        md.update(views_md_for(key, self.loader))
        md.scroll_home()
        self.notify(f"Onglet « {key} » rechargé.")


def views_md_for(key: str, loader: Loader) -> str:
    for k, _, builder in VIEWS:
        if k == key:
            return builder(loader)
    return ""
