import pkgutil
import importlib.util

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
app.title = "Simplex Solver"

app.layout = create_layout(app)

if __name__ == "__main__":
    app.run(debug=True, dev_tools_ui=False)
