"""
layout.py
---------
Defines the visual structure of the Dash application.
No callbacks here — only static component definitions.
"""

from dash import html, dcc
import dash_bootstrap_components as dbc
import dash_katex as dk
import os


def _read_ui_max_dim() -> int:
    raw = os.getenv("SIMPLEX_UI_MAX_DIM", "1000")
    try:
        parsed = int(raw)
    except ValueError:
        parsed = 30
    return max(10, min(1000, parsed))


UI_MAX_DIM = _read_ui_max_dim()


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
                className="d-none d-lg-block",
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
                className="d-none d-lg-block",
                style={
                    "position": "absolute",
                    "right": "20px",
                    "top": "50%",
                    "transform": "translateY(-50%)",
                    "textAlign": "right",
                }
            ),
        ],
        className="py-2 d-flex align-items-center position-fixed top-0 w-100",
        style={
            "color": "#303030",  # Primary blue
            "zIndex": 1030,
            "minHeight": "56px",
            # Đã giảm độ opacity từ 0.86 xuống 0.5 để lớp kính trong suốt hơn
            "backgroundColor": "rgba(255, 255, 255, 0.5)", 
            "backdropFilter": "blur(8px) saturate(125%)",
            "WebkitBackdropFilter": "blur(8px) saturate(125%)",
            "borderBottom": "1px solid #d1d5db",
            "boxShadow": "0 6px 16px rgb        a(8, 46, 110, 0.28)",
        },
    )

    # ── Step 1: Problem size + goal ───────────────────────────────────────
    config_card = _card(
        "1. Cấu hình bài toán",
        dbc.Row([
            dbc.Col([
                dbc.Label("Chế độ giải"),
                dbc.Select(
                    id="mode-select",
                    options=[
                        {"label": "Learning (chi tiết)", "value": "learning"},
                        {"label": "Production (gọn, nhanh)", "value": "production"},
                    ],
                    value="learning",
                ),
            ], md=3),
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
            ], md=3),
            dbc.Col([
                dbc.Label("Số biến (n)"),
                dbc.Input(
                    id="num-vars",
                    type="number",
                    min=1, max=UI_MAX_DIM, step=1, value=2,
                    placeholder="2",
                ),
                dbc.FormText(f"Giới hạn hiện tại: {UI_MAX_DIM}"),
            ], md=3),
            dbc.Col([
                dbc.Label("Số ràng buộc (m)"),
                dbc.Input(
                    id="num-constraints",
                    type="number",
                    min=1, max=UI_MAX_DIM, step=1, value=2,
                    placeholder="2",
                ),
                dbc.FormText(f"Giới hạn hiện tại: {UI_MAX_DIM}"),
            ], md=3),
        ]),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Switch(
                        id="show-normalized-model",
                        label="Hiện mô hình đã chuẩn hóa",
                        value=True,
                    ),
                    md=6,
                    className="mt-2",
                )
            ]
        ),
    )

    # ── Step 2: Objective function + constraints (generated dynamically) ──
    input_card = _card(
        "2. Nhập hàm mục tiêu & ràng buộc",
        html.Div(
            id="lp-input-zone",
            children=[
                # Objective row
                dbc.Row([
                    dbc.Col(
                        dbc.Label(
                            [
                                html.Span("Hàm mục tiêu: ", className="me-1"),
                                dk.DashKatex(expression=r"Z =", displayMode=False),
                            ],
                            className="fw-bold d-flex align-items-center",
                        ),
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
                                type="text",
                                inputMode="decimal",
                                placeholder="hằng số d",
                                style={"width": "100px"},
                                size="sm",
                            ),
                        ], className="mb-1"),
                        width="auto",
                        className="d-flex align-items-center",
                    ),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col(
                        dbc.Label(
                            [
                                html.Span("Miền dấu biến (", className="me-1"),
                                dk.DashKatex(expression=r"x_j", displayMode=False),
                                html.Span("):", className="ms-1"),
                            ],
                            className="fw-semibold d-flex align-items-center",
                        ),
                        width="auto",
                        className="d-flex align-items-center",
                    ),
                    dbc.Col(html.Div(id="variable-sign-inputs")),
                ], className="mb-2"),
                html.Div(
                    dk.DashKatex(
                        expression=r"x_j \ge 0\;\text{(không âm)}\quad\text{or}\quad x_j \in \mathbb{R}\;\text{(tự do)}",
                        displayMode=False,
                    ),
                    className="text-muted small mb-2",
                ),
                html.Hr(),
                # Constraint rows (injected by callback)
                html.Div(id="constraint-inputs"),
            ],
        ),
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
        # Default to table view for faster first render on medium/large models.
        dcc.Store(id="display-mode", data="table"),
        dcc.Store(id="steps-store",  data=None),
        dcc.Store(id="_hover-dummy", data=""),
        # Keep algebra panel collapsed initially to avoid heavy initial UI render.
        dcc.Store(id="algebra-panel-visible", data=False),
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
            [
                html.Div(
                    [
                        # Phần bên trái: Tên môn học & Bản quyền
                        html.Span("© 2026 Kỹ thuật ra Quyết định - EE3145", className="fw-bold"),
                        html.Span(" | Phát triển Web App phương pháp Đơn hình ứng dụng cho học tập", className="ms-2 d-none d-sm-inline"),
                    ],
                    className="text-muted small",
                ),
                html.Div(
                    [
                        # Phần bên phải: Số phiên bản
                        html.Span("Version: ", className="text-muted me-1"),
                        dbc.Badge("2.1", color="primary", className="rounded-pill"),
                    ],
                    className="small",
                ),
            ],
            className="container-fluid d-flex justify-content-between align-items-center py-2 px-4",
        ),
        className="position-fixed w-100 bottom-0 bg-white border-top shadow-sm",
        style={
            "zIndex": 1030,
            "backdropFilter": "blur(5px)",  # Tạo hiệu ứng mờ kính nhẹ cho hiện đại
            "backgroundColor": "rgba(255, 255, 255, 0.4)",  # Làm nền hơi trong suốt
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
                    html.Img(src="/assets/Math.svg", style={"width": "28px", "height": "28px"}),
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
