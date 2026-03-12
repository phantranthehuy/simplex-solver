"""
layout.py
---------
Defines the visual structure of the Dash application.
No callbacks here — only static component definitions.
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
import dash_katex as dk


# ── Reusable card wrapper ─────────────────────────────────────────────────
def _card(title, *children):
    return dbc.Card(
        dbc.CardBody([html.H5(title, className="card-title mb-3"), *children]),
        className="mb-4 shadow-sm",
    )


def create_layout(app):
    """Return the top-level layout component."""

    # ── Header ────────────────────────────────────────────────────────────
    logo = html.Img(
        src=app.get_asset_url("bk_name_en.png"),
        height="36px",
    )
    header = html.Div(
        [
            html.Div(
                logo,
                style={
                    "position": "absolute",
                    "left": "20px",
                    "top": "50%",
                    "transform": "translateY(-50%)"
                }
            ),
            html.Div(
                html.H3(
                    "Simplex Solver",
                    className="mb-0 fw-bold",
                ),
                className="text-center w-100",
            ),
            html.Div(
                [
                    html.Div("Sinh viên thực hiện: Phan Trần Thế Huy", className="small lh-1"),
                    html.Div("MSSV: 2211259", className="small lh-1 mt-1"),
                ],
                style={
                    "position": "absolute",
                    "right": "20px",
                    "top": "50%",
                    "transform": "translateY(-50%)",
                    "textAlign": "right",
                }
            ),
        ],
        className="bg-primary text-white py-2 d-flex align-items-center position-fixed top-0 w-100 shadow",
        style={"zIndex": 1030, "minHeight": "56px"},
    )

    # ── Step 1: Problem size + goal ───────────────────────────────────────
    config_card = _card(
        "1. Cấu hình bài toán",
        dbc.Row([
            dbc.Col([
                dbc.Label("Mục tiêu"),
                dbc.Select(
                    id="goal-select",
                    options=[
                        {"label": "Tối đa (Max)", "value": "max"},
                        {"label": "Tối thiểu (Min)", "value": "min"},
                    ],
                    value="max",
                ),
            ], md=4),
            dbc.Col([
                dbc.Label("Số biến (n)"),
                dbc.Input(
                    id="num-vars",
                    type="number",
                    min=1, max=10, step=1, value=2,
                    placeholder="2",
                ),
            ], md=4),
            dbc.Col([
                dbc.Label("Số ràng buộc (m)"),
                dbc.Input(
                    id="num-constraints",
                    type="number",
                    min=1, max=10, step=1, value=2,
                    placeholder="2",
                ),
            ], md=4),
        ]),
    )

    # ── Step 2: Objective function + constraints (generated dynamically) ──
    input_card = _card(
        "2. Nhập hàm mục tiêu & ràng buộc",
        # Objective row
        dbc.Row([
            dbc.Col(
                dbc.Label("Hàm mục tiêu:  Z = ", className="fw-bold"),
                width="auto",
                className="d-flex align-items-center",
            ),
            dbc.Col(
                html.Div(id="objective-inputs"),
            ),
            dbc.Col(
                dbc.InputGroup([
                    dbc.InputGroupText("+"),
                    dbc.Input(
                        id="obj-constant",
                        type="number",
                        placeholder="hằng số d",
                        style={"width": "100px"},
                        size="sm",
                    ),
                ], className="mb-1"),
                width="auto",
                className="d-flex align-items-center",
            ),
        ], className="mb-3"),
        html.Hr(),
        # Constraint rows (injected by callback)
        html.Div(id="constraint-inputs"),
    )

    # ── Step 3: Action buttons + display toggle ───────────────────────────
    action_row = dbc.Row([
        dbc.Col(
            dbc.Button(
                "Giải",
                id="btn-solve",
                color="primary",
                size="lg",
                className="w-100",
            ),
            md=4,
        ),
        # Hidden stores
        dcc.Store(id="display-mode", data="algebra"),
        dcc.Store(id="steps-store",  data=None),
        dcc.Store(id="_hover-dummy", data=""),
        dcc.Store(id="algebra-panel-visible", data=True),
    ], justify="center", className="mb-4"),

    # ── Step 4: Result area (filled by callbacks) ─────────────────────────
    result_card = dbc.Card(
        dbc.CardBody([
            # Card title row with eye button at top-right
            html.Div(
                [
                    html.H5("3. Kết quả", className="card-title mb-0"),
                    dbc.Button(
                        html.Img(
                            src=app.get_asset_url("visibility.svg"),
                            id="btn-toggle-algebra-img",
                            style={"width": "22px", "height": "22px"},
                        ),
                        id="btn-toggle-algebra",
                        color="link",
                        size="sm",
                        className="p-0",
                        style={"lineHeight": "1", "display": "none"},
                    ),
                ],
                className="d-flex justify-content-between align-items-center mb-3",
            ),
            dbc.Spinner(
                html.Div(
                    id="result-area",
                    children=html.P(
                        'Hãy nhấn "Giải" để xem kết quả.',
                        className="text-muted fst-italic",
                    ),
                ),
                color="primary",
                size="sm",
            ),
        ]),
        className="mb-4 shadow-sm",
    )

    # ── Footer ────────────────────────────────────────────────────────────
    footer = html.Footer(
        html.Div(
            "Kỹ thuật ra Quyết định EE3145",
            className="text-center text-muted small py-2",
        ),
        className="position-fixed w-100 bottom-0 bg-white border-top shadow-sm",
        style={
            "zIndex": 1030,
        },
    )

    # ── Main content container (cards) ─────────────────────────────────────
    content = dbc.Container(
        [
            config_card,
            input_card,
            *action_row,
            result_card,
        ],
        fluid=True,
        className="py-3",
        style={"maxWidth": "1400px", "marginTop": "72px", "marginBottom": "60px"},
    )

    # ── Assemble page ─────────────────────────────────────────────────────
    return html.Div(
        [
            # Header full-width fixed
            header,
            # Centered, wider cards
            content,
            # Footer full-width fixed
            footer,
            # Floating mode-toggle FAB (bottom-left)
            html.Div(
                dbc.Button(
                    html.Img(src="/assets/Table.svg", style={"width": "28px", "height": "28px"}),
                    id="btn-toggle-mode",
                    color="secondary",
                    style={
                        "borderRadius": "50%",
                        "width": "52px",
                        "height": "52px",
                        "padding": "0",
                        "display": "flex",
                        "alignItems": "center",
                        "justifyContent": "center",
                        "boxShadow": "0 4px 12px rgba(0,0,0,0.25)",
                        "transition": "all 0.2s ease",
                    },
                ),
                style={
                    "position": "fixed",
                    "bottom": "72px",
                    "left": "24px",
                    "zIndex": 1050,
                },
            ),
        ],
    )
