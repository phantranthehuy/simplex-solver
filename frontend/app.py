import pkgutil
import importlib.util
import os
import sys
from pathlib import Path

# Ensure project root is importable when launching with: python frontend/app.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# pkgutil.find_loader was removed in Python 3.14; patch it back for Dash compatibility
if not hasattr(pkgutil, "find_loader"):
    def _find_loader(name):
        try:
            spec = importlib.util.find_spec(name)
            return spec.loader if spec else None
        except (ValueError, ModuleNotFoundError):
            return None
    pkgutil.find_loader = _find_loader

import dash
import dash_bootstrap_components as dbc

from layout import create_layout
import callbacks  # noqa: F401 — registers callbacks

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
)

server = app.server

app.title = "Simplex Solver"

app.layout = create_layout(app)

if __name__ == "__main__":
    host = os.getenv("FRONTEND_HOST", "127.0.0.1")
    port = int(os.getenv("FRONTEND_PORT", "8050"))
    debug = os.getenv("FRONTEND_DEBUG", "1").lower() in {"1", "true", "yes", "on"}
    app.run(debug=debug, dev_tools_ui=False, host=host, port=port)
