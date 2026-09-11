"""Point d'entrée : `python -m dashboard` (venv polyenv)."""
from .app import DashboardApp


def main() -> None:
    DashboardApp().run()


if __name__ == "__main__":
    main()
