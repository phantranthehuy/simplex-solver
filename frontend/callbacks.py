"""
callbacks.py
------------
Dash callbacks — all interactivity logic.
"""

import os
import json
import numpy as np

from dash import Input, Output, State, ALL, callback, clientside_callback, html
import dash_bootstrap_components as dbc
import dash_katex as dk

from api_client import request_solver_result
from legacy.old_system.latex_helper import (
    format_objective,
    format_standard_form,
    format_pivot_choice,
    format_updated_equations,
    format_w_objective,
    _var_label,
)


def _read_ui_max_dim() -> int:
    raw = os.getenv("SIMPLEX_UI_MAX_DIM", "1000")
    try:
        parsed = int(raw)
    except ValueError:
        parsed = 30
    return max(10, min(1000, parsed))


UI_MAX_DIM = _read_ui_max_dim()


# ── UI micro-helpers ────────────────────────────────────────────────────

_SUB_TRANS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
def _sub(n: int) -> str:
    """Convert integer to Unicode subscript string, e.g. 12 → '₁₂'."""
    return str(n).translate(_SUB_TRANS)

def _xsub(j: int):
    """Return an inline math label for x_j."""
    return dk.DashKatex(expression=_var_label(f"x{j}"), displayMode=False)

def _step_header(
    step_num: int,
    title: str,
    tooltip_text=None,
    uid: str = "",
    tooltip_content=None,
):
    """Numbered step title with hover tooltip."""
    if tooltip_content is None:
        tooltip_content = tooltip_text
    if tooltip_content is None:
        tooltip_content = ""

    tid = f"tt-{uid}"
    return html.Div([
        html.Span(
            f"Bước {step_num}: {title}",
            id=tid,
            className="fw-semibold text-primary d-inline-block",
            style={"cursor": "help", "borderBottom": "1px dashed #0d6efd"},
        ),
        dbc.Tooltip(tooltip_content, target=tid, placement="top"),
    ], className="mt-3 mb-1")


def _hover_term(label: str, tooltip_text=None, uid: str = "", tooltip_content=None):
    """Inline term with hover tooltip used for glossary-like hints."""
    if tooltip_content is None:
        tooltip_content = tooltip_text
    if tooltip_content is None:
        tooltip_content = ""

    tid = f"term-tt-{uid}"
    return html.Span([
        html.Span(
            label,
            id=tid,
            style={"cursor": "help", "borderBottom": "1px dotted #6c757d"},
        ),
        dbc.Tooltip(tooltip_content, target=tid, placement="top"),
    ], className="d-inline-flex align-items-center")


def _math(expr: str):
    """Inline KaTeX block inside a light card."""
    return dbc.Card(
        dbc.CardBody(dk.DashKatex(expression=expr), className="py-2 px-3"),
        className="bg-light border-0 mb-2",
    )


def _math_list(exprs):
    return html.Div([_math(e) for e in exprs])


def _fmt(val: float) -> str:
    """Float → clean string (no trailing .0)."""
    return str(int(val)) if float(val) == int(val) else f"{val:.4g}"


def _unbounded_payload(step, var_names):
    """Collect entering-column and ratio-test diagnostics for unbounded conclusions."""
    pivot_col = step.get("pivot_col")
    tableau = np.asarray(step.get("tableau"), dtype=float)
    basis = list(step.get("basis") or [])

    if pivot_col is None or tableau.ndim != 2 or tableau.shape[0] <= 1:
        return {
            "entering_name": "?",
            "entering_label": "?",
            "invalid_rows": [],
            "reason_text": "không có hàng pivot hợp lệ",
        }

    entering_name = var_names[pivot_col] if pivot_col < len(var_names) else f"x{pivot_col + 1}"
    invalid_rows = []
    for i in range(1, tableau.shape[0]):
        a_val = float(tableau[i, pivot_col])
        if a_val <= 1e-10:
            bname = basis[i - 1] if i - 1 < len(basis) else f"hàng {i}"
            invalid_rows.append({"row": i, "basis": bname, "a": a_val})

    if invalid_rows:
        pieces = [
            f"{item['basis']}: a={_fmt(item['a'])} <= 0"
            for item in invalid_rows
        ]
        reason_text = " ; ".join(pieces)
    else:
        reason_text = "mọi hàng đều cho tỷ số không hợp lệ"

    return {
        "entering_name": entering_name,
        "entering_label": _var_label(entering_name),
        "invalid_rows": invalid_rows,
        "reason_text": reason_text,
    }


def _unbounded_tooltip_text(step, var_names):
    info = _unbounded_payload(step, var_names)
    return html.Div(
        [
            html.Div(
                [
                    html.Span("Cột biến vào "),
                    dk.DashKatex(expression=info["entering_label"], displayMode=False),
                    html.Span(" không có hàng pivot hợp lệ."),
                ],
                className="d-flex align-items-center flex-wrap gap-1",
            ),
            html.Div(
                [
                    html.Span("Min-ratio test thất bại vì "),
                    dk.DashKatex(expression=r"a_{ij} \le 0\ \forall i", displayMode=False),
                    html.Span(", nên "),
                    dk.DashKatex(expression=r"|Z|\to\infty", displayMode=False),
                    html.Span("."),
                ],
                className="d-flex align-items-center flex-wrap gap-1",
            ),
        ],
        className="tooltip-math",
    )


def _unbounded_alert_components(step, var_names, detail_level="compact"):
    info = _unbounded_payload(step, var_names)

    if info["invalid_rows"]:
        detail_expr = r";\ ".join(
            rf"{_var_label(item['basis'])}:\ a_{{ij}} = {_fmt(item['a'])}\le 0"
            for item in info["invalid_rows"]
        )
    else:
        detail_expr = r"\text{mọi hàng đều cho tỷ số không hợp lệ}"

    compact = [
        html.Span(
            [
                html.Span("Cột"),
                dk.DashKatex(expression=info["entering_label"], displayMode=False),
                html.Span("không có hàng pivot hợp lệ."),
                dk.DashKatex(
                    expression=r"a_{ij} \leq 0\ \forall i\ \Rightarrow\ \theta_i\ \text{không hợp lệ}\ \Rightarrow\ |Z| \to \infty",
                    displayMode=False,
                ),
            ],
            className="unbounded-inline",
        )
    ]

    if detail_level == "compact":
        return compact

    medium = compact + [
        html.Div(
            dk.DashKatex(
                expression=rf"\text{{Min-ratio test thất bại theo từng hàng: }}\ {detail_expr}",
                displayMode=False,
            ),
            className="unbounded-inline unbounded-detail mt-1",
        )
    ]
    if detail_level == "medium":
        return medium

    return medium + [
        html.Div(
            dk.DashKatex(
                expression=r"\text{Suy ra không tồn tại biến rời cơ sở, nên có một tia khả thi làm }\ |Z|\to\infty",
                displayMode=False,
            ),
            className="unbounded-inline unbounded-detail mt-1",
        ),
    ]


def _is_missing(value) -> bool:
    """Treat None or blank strings as missing input."""
    return value is None or (isinstance(value, str) and value.strip() == "")


def _parse_decimal(value, field_name: str) -> float:
    """
    Parse numeric input from UI text boxes.
    Accept both dot and comma decimal separators.
    """
    if _is_missing(value):
        raise ValueError(f"Thiếu giá trị {field_name}")

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().replace(",", ".")
    return float(text)


def _normalize_var_sign(value) -> str:
    """Normalize UI variable-sign labels to backend enum tokens."""
    token = str(value).strip().lower() if value is not None else "nonnegative"
    aliases = {
        "nonnegative": "nonnegative",
        "không âm": "nonnegative",
        "x >= 0": "nonnegative",
        "free": "free",
        "tự do": "free",
        "x tự do": "free",
    }
    return aliases.get(token, token)


def _latex_op(op: str) -> str:
    return {"<=": r"\leq", ">=": r"\geq", "=": "="}.get(op, "=")


def _latex_linear_expr(coeffs, var_names) -> str:
    parts = []
    for j, c in enumerate(coeffs):
        coef = float(c)
        if abs(coef) <= 1e-12:
            continue

        label = _var_label(var_names[j]) if j < len(var_names) else _var_label(f"x{j+1}")
        abs_c = abs(coef)
        coeff_txt = "" if abs(abs_c - 1.0) <= 1e-12 else _fmt(abs_c)
        term = f"{coeff_txt}{label}" if coeff_txt else label

        if not parts:
            parts.append(term if coef > 0 else f"-{term}")
        else:
            sign = "+" if coef > 0 else "-"
            parts.append(f" {sign} {term}")

    return "".join(parts) if parts else "0"


def _render_normalized_model_notice(model: dict):
    if not isinstance(model, dict):
        return None

    objective = model.get("objective") or []
    constraints = model.get("constraints") or []
    types = model.get("types") or []
    var_names = model.get("decision_var_names") or [f"x{j+1}" for j in range(len(objective))]
    goal = (model.get("goal") or "max").lower()

    if not objective or not constraints:
        return None

    obj_expr = _latex_linear_expr(objective, var_names)
    goal_cmd = r"\max" if goal == "max" else r"\min"
    obj_line = rf"{goal_cmd}\ Z = {obj_expr}"

    con_lines = []
    for i, row in enumerate(constraints):
        if not isinstance(row, list) or len(row) < 1:
            continue
        coeffs = row[:-1]
        rhs_val = row[-1]
        op = types[i] if i < len(types) else "="
        lhs = _latex_linear_expr(coeffs, var_names)
        con_lines.append(rf"{lhs}\ {_latex_op(op)}\ {_fmt(rhs_val)}")

    con_blocks = [
        html.Div(
            [html.Span(f"C{i+1}: ", className="me-2"), dk.DashKatex(expression=expr, displayMode=False)],
            className="mb-1 d-flex align-items-center flex-wrap",
        )
        for i, expr in enumerate(con_lines)
    ]

    return dbc.Alert(
        [
            html.Div("Mô hình đã chuẩn hóa:", className="fw-semibold mb-2"),
            html.Div(
                [
                    html.Div(
                        [html.Span("Objective: ", className="me-2"), dk.DashKatex(expression=obj_line, displayMode=False)],
                        className="mb-2 d-flex align-items-center flex-wrap",
                    ),
                    *con_blocks,
                ]
            ),
        ],
        color="secondary",
        className="mb-3",
    )


def _phase1_artificial_vars(first_phase_step: dict, fallback_var_names) -> list:
    """Get artificial variables for Phase 1 even when backend does not send art_vars."""
    if not isinstance(first_phase_step, dict):
        return []

    art_vars = first_phase_step.get("art_vars") or []
    if art_vars:
        return [v for v in art_vars if isinstance(v, str) and v.startswith("a")]

    phase1_var_names = first_phase_step.get("var_names") or fallback_var_names or []
    return [v for v in phase1_var_names if isinstance(v, str) and v.startswith("a")]


def _art_vars_latex(art_vars: list) -> str:
    if art_vars:
        return ", ".join(_var_label(v) for v in art_vars)
    return r"\text{biến nhân tạo}"


def _should_show_normalized_model_notice(normalized_model: dict, normalization: dict, input_echo: dict) -> bool:
    """Show the normalized-model card only when Stage-1 actually changed the model."""
    if not isinstance(normalized_model, dict):
        return False

    normalization = normalization if isinstance(normalization, dict) else {}
    input_echo = input_echo if isinstance(input_echo, dict) else {}

    rhs_flips = normalization.get("rhs_flips") or []
    substitutions = normalization.get("unrestricted_substitutions") or []
    presolve = normalization.get("presolve") or {}
    presolve_scaling = (presolve.get("scaling") or []) if isinstance(presolve, dict) else []
    presolve_removed = (presolve.get("removed_constraints") or []) if isinstance(presolve, dict) else []

    if rhs_flips or substitutions or presolve_removed:
        return True

    scaling_only = bool(presolve_scaling)

    # If no explicit normalization metadata exists and no input echo is available,
    # avoid showing the card by default.
    if not input_echo:
        return False

    in_objective = input_echo.get("objective") or []
    in_constraints = input_echo.get("constraints") or []
    in_rhs = input_echo.get("rhs") or []
    in_types = input_echo.get("types") or []
    in_goal = str(input_echo.get("goal") or "").strip().lower()

    norm_objective = normalized_model.get("objective") or []
    norm_constraints = normalized_model.get("constraints") or []
    norm_types = normalized_model.get("types") or []
    norm_goal = str(normalized_model.get("goal") or "").strip().lower()

    def _close(a, b, eps=1e-9):
        return abs(float(a) - float(b)) <= eps

    def _positive_proportional(row_a, row_b, eps=1e-9):
        if len(row_a) != len(row_b):
            return False
        scale = None
        for a, b in zip(row_a, row_b):
            a = float(a)
            b = float(b)
            if abs(a) <= eps and abs(b) <= eps:
                continue
            if abs(a) <= eps or abs(b) <= eps:
                return False
            ratio = b / a
            if ratio <= eps:
                return False
            if scale is None:
                scale = ratio
            elif abs(ratio - scale) > 1e-7:
                return False
        return scale is not None

    try:
        in_obj = [float(v) for v in in_objective]
        norm_obj = [float(v) for v in norm_objective]
    except (TypeError, ValueError):
        return True

    if len(in_obj) != len(norm_obj):
        return True
    if any(not _close(a, b) for a, b in zip(in_obj, norm_obj)):
        return True

    if in_goal and norm_goal and in_goal != norm_goal:
        return True

    if len(in_constraints) != len(in_rhs):
        return True

    input_rows = []
    try:
        for row, rhs_val in zip(in_constraints, in_rhs):
            if not isinstance(row, list):
                return True
            input_rows.append([float(v) for v in row] + [float(rhs_val)])
    except (TypeError, ValueError):
        return True

    if len(input_rows) != len(norm_constraints):
        return True

    try:
        for row_in, row_norm in zip(input_rows, norm_constraints):
            if not isinstance(row_norm, list):
                return True
            norm_row = [float(v) for v in row_norm]
            if len(row_in) != len(norm_row):
                return True
            if any(not _close(a, b) for a, b in zip(row_in, norm_row)):
                if not (scaling_only and _positive_proportional(row_in, norm_row)):
                    return True
    except (TypeError, ValueError):
        return True

    in_types_norm = [str(t).strip() for t in in_types]
    norm_types_norm = [str(t).strip() for t in norm_types]
    if in_types_norm != norm_types_norm:
        return True

    return False


def _render_phase1_summary(steps, var_names):
    """
    Build a compact UI summary of Phase 1 (finding a BFS).

    Returns (blocks, feasible) where feasible is True if Phase 1 succeeded.
    """
    p1_steps = [s for s in steps if s["step_name"].startswith("Pha 1")]
    if not p1_steps:
        return [], True

    p1_vn  = p1_steps[0].get("var_names") or var_names
    blocks = []
    blocks.append(dbc.Badge(
        "Pha 1 \u2014 T\u00ecm l\u1eddi gi\u1ea3i c\u01a1 s\u1edf kh\u1ea3 thi (BFS)",
        color="warning", pill=True,
        className="fs-6 mb-3 px-3 py-2",
        style={"color": "#664d03"},
    ))
    blocks.append(dbc.Alert([
        html.Span(
            "R\u00e0ng bu\u1ed9c d\u1ea1ng '=' kh\u00f4ng c\u00f3 bi\u1ebfn b\u00f9 t\u1ef1 nhi\u00ean \u2192 "
            "th\u00eam bi\u1ebfn nh\u00e2n t\u1ea1o a\u1d62. Pha 1 t\u1ed1i thi\u1ec3u h\u00f3a t\u1ed5ng bi\u1ebfn nh\u00e2n t\u1ea1o "
            "\u0111\u1ec3 t\u00ecm BFS cho Pha 2."
        ),
        html.Div(dk.DashKatex(expression=r"W = \sum_i a_i \to 0", displayMode=False), className="mt-1"),
    ], color="warning", className="mb-3"))

    p1_pivots = [s for s in p1_steps if s["pivot_row"] is not None]
    for p1_idx, p1s in enumerate(p1_pivots, start=1):
        entering_v = p1_vn[p1s["pivot_col"]]
        leaving_v  = p1s["basis"][p1s["pivot_row"] - 1]
        blocks.append(html.Div([
            dbc.Badge(f"Pha 1 \u2014 L\u1ea7n l\u1eb7p {p1_idx}", color="secondary",
                      pill=True, className="me-2"),
            html.Span("Bi\u1ebfn v\u00e0o: "),
            dk.DashKatex(expression=_var_label(entering_v)),
            html.Span(", Bi\u1ebfn ra: ", className="ms-2"),
            dk.DashKatex(expression=_var_label(leaving_v)),
        ], className="d-flex align-items-center flex-wrap gap-1 mb-2 ms-2"))

    p1_end = p1_steps[-1]
    if "V\u00f4 nghi\u1ec7m" in p1_end["step_name"]:
        blocks.append(dbc.Alert(
            [
                html.Span("\u274c Pha 1 k\u1ebft th\u00fac: "),
                dk.DashKatex(expression=r"W^* \neq 0", displayMode=False),
                html.Span(" \u2192 B\u00e0i to\u00e1n v\u00f4 nghi\u1ec7m."),
            ],
            color="danger", className="mb-3",
        ))
        return blocks, False

    blocks.append(dbc.Alert(
        [
            html.Span("\u2705 Pha 1 ho\u00e0n th\u00e0nh: t\u1ea5t c\u1ea3 bi\u1ebfn nh\u00e2n t\u1ea1o "),
            dk.DashKatex(expression=r"a_i = 0", displayMode=False),
            html.Span(" \u2192 BFS kh\u1ea3 thi. Lo\u1ea1i b\u1ecf c\u1ed9t bi\u1ebfn nh\u00e2n t\u1ea1o, chuy\u1ec3n sang Pha 2."),
        ],
        color="success", className="mb-3",
    ))
    blocks.append(dbc.Badge(
        "Pha 2 \u2014 T\u1ed1i \u01b0u h\u00f3a h\u00e0m m\u1ee5c ti\u00eau g\u1ed1c",
        color="warning", pill=True,
        className="fs-6 mb-3 px-3 py-2",
        style={"color": "#664d03"},
    ))
    return blocks, True


# ── Table-mode renderer ─────────────────────────────────────────────────

def render_tableau_static(step, var_names, z_offset=0.0, obj_label="Z", goal="max"):
    """
    Render one Simplex tableau step as an html.Table.

    Columns: Basis | <var_names...> | b | Ratio

    Parameters
    ----------
    step      : dict   — one element from solve_steps()
    var_names : list   — all variable names in column order
    z_offset  : float  — constant to add to objective row RHS
    obj_label : str    — label for objective row ("Z" or "W")

    Returns
    -------
    html.Table
    """
    tableau   = step["tableau"]
    basis     = step["basis"]
    ratios    = step["ratios"]   # list[float|None] or None
    pivot_row = step.get("pivot_row")  # 1-based tableau row index, or None
    pivot_col = step.get("pivot_col")  # 0-based variable column index, or None
    n_vars    = len(var_names)
    m         = tableau.shape[0] - 1   # number of constraint rows

    def _cell(val):
        """Format a float to 2 decimal places (string)."""
        return f"{float(val):.2f}"

    def _cell_katex(val):
        """Return a KaTeX component for a numeric cell."""
        return dk.DashKatex(expression=_cell(val))

    def _cls(tbl_row, tbl_col, extra=""):
        """Return the CSS class string for a data cell."""
        in_pr = pivot_row is not None and tbl_row == pivot_row
        in_pc = pivot_col is not None and tbl_col == pivot_col
        if in_pr and in_pc:
            base = "pivot-cell pcol-cell"
        elif in_pr:
            base = "pivot-row"
        elif in_pc:
            base = "pivot-col pcol-cell"
        else:
            base = ""
        return (base + " " + extra).strip() or None

    # ── Header row ────────────────────────────────────────────────────────
    # Ratio header: wrap in a span with a unique id so Tooltip can target it.
    ratio_th_id = f"ratio-th-{id(step)}"
    ratio_header = html.Th(
        [
            html.Span("Ratio", id=ratio_th_id,
                      style={"cursor": "help",
                             "borderBottom": "1px dashed #90a4ae"}),
            dbc.Tooltip(
                "theta_i = b_i / a_ij, a_ij > 0",
                target=ratio_th_id,
                placement="top",
            ),
        ],
        scope="col",
        className="tableau-ratio",
    )
    header_cells = [html.Th(dk.DashKatex(expression="\\text{Basis}"), scope="col")]
    for v in var_names:
        header_cells.append(html.Th(dk.DashKatex(expression=_var_label(v)), scope="col"))
    header_cells.append(html.Th(dk.DashKatex(expression="b"), scope="col"))
    header_cells.append(ratio_header)

    # ── Constraint rows ───────────────────────────────────────────────────
    # tbl_row for constraint i (0-based) is i+1; tbl_col for var j is j;
    # the "b" column is the last tableau column (never == pivot_col).
    _NO_COL = -1   # sentinel: «not a variable column»
    body_rows = []
    for i in range(m):
        tbl_row = i + 1
        in_pr   = pivot_row is not None and tbl_row == pivot_row

        # Basis cell (variable name with subscript)
        basis_label = _var_label(basis[i]) if basis[i] is not None else "\\text{?}"
        cells = [html.Td(dk.DashKatex(expression=basis_label),
                         className=_cls(tbl_row, _NO_COL))]

        # Variable cells — add data-row to pivot-column cells for hover linking
        for j in range(n_vars):
            in_pc = pivot_col is not None and j == pivot_col
            kw    = {"data-row": str(i)} if in_pc else {}
            cells.append(html.Td(_cell_katex(tableau[tbl_row, j]),
                                  className=_cls(tbl_row, j), **kw))

        # b cell — always tagged for hover linking
        b_cls = "pivot-row b-cell" if in_pr else "b-cell"
        cells.append(html.Td(_cell_katex(tableau[tbl_row, -1]),
                              className=b_cls,
                              **{"data-row": str(i)}))

        # Ratio cell — numeric value, title tooltip, and data-row
        is_min    = in_pr
        ratio_cls = " ".join(filter(None, [
            "ratio-cell", "tableau-ratio", "min-ratio" if is_min else "",
        ]))
        if ratios is not None and i < len(ratios):
            r = ratios[i]
            if r is None or pivot_col is None:
                ratio_text  = "\u2014"
                ratio_title = "a \u2264 0 \u2014 kh\u00f4ng h\u1ee3p l\u1ec7"
            else:
                b_val       = tableau[tbl_row, -1]
                a_val       = tableau[tbl_row, pivot_col]
                ratio_title = f"{_cell(b_val)} / {_cell(a_val)} = {_cell(r)}"
                ratio_text  = _cell(r)
        else:
            ratio_text  = "\u2014"
            ratio_title = ""
        # Ratio cell: số hoặc dấu gạch ngang, hiển thị bằng KaTeX nếu là số
        ratio_child = (
            dk.DashKatex(expression=ratio_text)
            if ratio_text != "\u2014"
            else ratio_text
        )
        cells.append(html.Td(
            ratio_child,
            className=ratio_cls,
            title=ratio_title,
            **{"data-row": str(i)},
        ))
        body_rows.append(html.Tr(cells))

    # ── Objective (Z / W) row ────────────────────────────────────────────
    z_cells = [html.Td(dk.DashKatex(expression=obj_label))]
    for j in range(n_vars):
        z_cells.append(html.Td(_cell_katex(tableau[0, j])))
    z_rhs = tableau[0, -1]
    if goal == "min" or obj_label == "W":
        z_rhs = -z_rhs
    z_cells.append(html.Td(_cell_katex(z_rhs + z_offset)))
    z_cells.append(html.Td("", className="tableau-ratio"))
    body_rows.append(html.Tr(z_cells, className="tableau-z-row"))

    return html.Table(
        [html.Thead(html.Tr(header_cells)), html.Tbody(body_rows)],
        className="simplex-tableau table table-bordered table-sm mx-auto",
        style={"fontFamily": "monospace", "width": "auto"},
    )


def render_table_mode(steps, var_names, obj_constant=0.0, goal="max"):
    """
    Render all Simplex steps as a sequence of labelled, tooltipped tableau tables.
    """
    _COLOR_HEX = {
        "success":   "#198754",
        "danger":    "#dc3545",
        "secondary": "#6c757d",
        "primary":   "#0d6efd",
    }

    # Count decision variables (x1, x2, ...) for the conclusion line
    n_dec = sum(1 for v in var_names if v.startswith("x"))

    def _tooltip_text(step, idx):
        """Return a short theory summary for the step header tooltip."""
        name = step.get("step_name", "")
        if name == "Bảng ban đầu":
            return html.Div(
                [
                    html.Div("Thêm biến bù để đổi ràng buộc thành đẳng thức."),
                    html.Div(
                        [
                            dk.DashKatex(expression=r"s_i \ge 0", displayMode=False),
                            html.Span(","),
                            dk.DashKatex(expression=r"x_j = 0", displayMode=False),
                            html.Span("."),
                        ],
                        className="d-flex align-items-center flex-wrap gap-1",
                    ),
                ],
                className="tooltip-math",
            )
        if name == "Nghiệm tối ưu":
            cmp_expr = r"\bar{C}_j \ge 0" if goal == "min" else r"\bar{C}_j \le 0"
            return html.Div(
                [
                    html.Span("Điều kiện tối ưu thỏa cho mọi biến không cơ sở: "),
                    dk.DashKatex(expression=cmp_expr, displayMode=False),
                    html.Span("."),
                ],
                className="tooltip-math d-flex align-items-center flex-wrap gap-1",
            )
        if name == "Không bị chặn":
            return _unbounded_tooltip_text(step, var_names)
        if name == "Vô nghiệm":
            return html.Div(
                [
                    html.Span("Biến nhân tạo vẫn còn trong cơ sở ở trạng thái dừng: "),
                    dk.DashKatex(expression=r"a_i \ne 0", displayMode=False),
                    html.Span("."),
                ],
                className="tooltip-math d-flex align-items-center flex-wrap gap-1",
            )
        # Iteration step — include entering/leaving info
        pc = step.get("pivot_col")
        pr = step.get("pivot_row")
        entering = var_names[pc] if pc is not None else "?"
        leaving  = step["basis"][pr - 1] if pr is not None else "?"
        entering_label = _var_label(entering)
        leaving_label = _var_label(leaving)
        return html.Div(
            [
                html.Div(
                    [
                        html.Span("Biến vào: "),
                        dk.DashKatex(expression=entering_label, displayMode=False),
                        html.Span(", Biến ra: "),
                        dk.DashKatex(expression=leaving_label, displayMode=False),
                        html.Span("."),
                    ],
                    className="d-flex align-items-center flex-wrap gap-1",
                ),
                html.Div(
                    [
                        html.Span("Dùng min-ratio test: "),
                        dk.DashKatex(expression=r"\theta_i = \frac{b_i}{a_{ij}},\ a_{ij}>0", displayMode=False),
                        html.Span("."),
                    ],
                    className="d-flex align-items-center flex-wrap gap-1",
                ),
            ],
            className="tooltip-math",
        )

    def _step_header(step, idx):
        """Centered divider with badge and tooltip."""
        name         = step.get("step_name", f"Step {idx}")
        badge_color  = (
            "success"   if name == "Nghiệm tối ưu"   else
            "danger"    if name in ("Không bị chặn", "Vô nghiệm") else
            "secondary" if name == "Bảng ban đầu"     else
            "primary"
        )
        line_color = _COLOR_HEX.get(badge_color, "#6c757d")
        badge_id   = f"tbl-hdr-{idx}-{id(step)}"

        return html.Div(
            [
                html.Div(style={
                    "flex": "1", "height": "2px",
                    "backgroundColor": line_color, "borderRadius": "1px",
                }),
                html.Span(
                    dbc.Badge(
                        name, id=badge_id,
                        color=badge_color, pill=True,
                        className="fs-6 px-3 py-2",
                        style={"cursor": "help", "whiteSpace": "nowrap"},
                    ),
                    className="mx-3",
                ),
                dbc.Tooltip(
                    _tooltip_text(step, idx),
                    target=badge_id,
                    placement="top",
                ),
                html.Div(style={
                    "flex": "1", "height": "2px",
                    "backgroundColor": line_color, "borderRadius": "1px",
                }),
            ],
            style={"display": "flex", "alignItems": "center", "width": "100%"},
            className="mb-3",
        )

    def _conclusion(step):
        """Build the ✅ / ❌ conclusion line for terminal steps."""
        name = step.get("step_name", "")
        if name == "Không bị chặn":
            return dbc.Alert(
                [html.Span("❌ Bài toán không bị chặn: "), *_unbounded_alert_components(step, var_names, "compact")],
                color="danger", className="mt-3 mb-0",
            )
        if name == "Vô nghiệm":
            return dbc.Alert(
                "❌ Bài toán vô nghiệm — hệ ràng buộc mâu thuẫn nhau.",
                color="danger", className="mt-3 mb-0",
            )
        if name == "Nghiệm tối ưu":
            t_opt   = step["tableau"]
            basis   = step["basis"]
            # Tableau luôn lưu giá trị của bài toán MAX (W = -Z_no_const).
            # Với Min: Z = -W + d; với Max: Z = W + d.
            z_raw   = t_opt[0, -1]
            if goal == "min":
                z_raw = -z_raw
            z_val   = z_raw + obj_constant
            # Collect decision-variable values từ các biến quyết định
            expr_parts = [rf"Z^{{*}} = {_fmt(z_val)}"]
            basis_set = set(basis)
            for ri, v in enumerate(basis, start=1):
                if v.startswith("x"):
                    expr_parts.append(
                        rf"{_var_label(v)} = {_fmt(t_opt[ri, -1])}"
                    )
            # Any decision variable not in basis = 0
            for v in var_names[:n_dec]:
                if v not in basis_set and v.startswith("x"):
                    expr_parts.append(rf"{_var_label(v)} = 0")
            expr = r",\quad ".join(expr_parts)
            return dbc.Alert(
                dk.DashKatex(expression=expr),
                color="success", className="mt-3 mb-0 fw-semibold",
            )
        return None

    # ── Build block list ──────────────────────────────────────────────────
    blocks: list = []
    for idx, step in enumerate(steps):
        name = step.get("step_name", f"Step {idx}")
        var_names = step.get("var_names") or var_names

        # For Phase 1 steps, render the Phase 1 tableau (W row) instead
        is_phase1 = step.get("phase") == 1
        if is_phase1 and "phase1_tab" in step:
            p1_step = {**step, "tableau": step["phase1_tab"]}
            block_children = [
                _step_header(step, idx),
                render_tableau_static(p1_step, var_names,
                                      z_offset=0.0, obj_label="W", goal=goal),
            ]
        else:
            block_children = [
                _step_header(step, idx),
                render_tableau_static(step, var_names,
                                      z_offset=obj_constant, goal=goal),
            ]

        conclusion = _conclusion(step)
        if conclusion:
            block_children.append(conclusion)

        blocks.append(html.Div(block_children, className="mb-4"))

        if name in ("Nghiệm tối ưu", "Không bị chặn", "Vô nghiệm"):
            break   # stop after terminal step

    return blocks


# ── Algebra-mode renderer (classic — dùng cho panel Bảng) ────────────────

def render_algebra_mode_classic(steps, var_names, goal, objective, obj_constant=0.0):
    """
    Trình bày dạng 7 bước có tooltip — dùng cho panel Giải thích Đại số
    bên trong chế độ Bảng.
    """
    n_dec = len(objective)
    blocks: list = []

    obj_latex = format_objective(objective, var_names[:n_dec], goal)
    if obj_constant:
        abs_c  = abs(obj_constant)
        c_str  = str(int(abs_c)) if abs_c == int(abs_c) else f"{abs_c:g}"
        sign   = "+" if obj_constant > 0 else "-"
        obj_latex += rf" {sign} {c_str}"
    blocks.append(dbc.Alert(
        [html.Strong("Hàm mục tiêu: "), dk.DashKatex(expression=obj_latex)],
        color="info", className="mb-3",
    ))

    # ── Split Phase 1 / Phase 2 ──────────────────────────────────────────
    p1_steps = [s for s in steps if s.get("phase") == 1]
    p2_steps = [s for s in steps if s.get("phase", 2) == 2]

    # ── Phase 1 concise decisions (table mode left panel) ─────────────────
    if p1_steps:
        p1_vn     = p1_steps[0].get("var_names") or var_names
        art_vars  = _phase1_artificial_vars(p1_steps[0], p1_vn)

        blocks.append(dbc.Badge(
            "Pha 1 — Tìm lời giải cơ sở khả thi (BFS)",
            color="warning", pill=True,
            className="fs-6 mb-3 px-3 py-2",
            style={"color": "#664d03"},
        ))
        blocks.append(dbc.Alert(
            html.Div([
                html.Span("Thêm biến thêm vào: "),
                dk.DashKatex(expression=_art_vars_latex(art_vars)),
                html.Span(". Mục tiêu: ", className="ms-1"),
                dk.DashKatex(expression=format_w_objective(art_vars)),
            ], className="d-flex align-items-center flex-wrap gap-1"),
            color="warning", className="mb-3"
        ))

        p1_pivots = [s for s in p1_steps if s["pivot_row"] is not None]
        for p1_idx, p1s in enumerate(p1_pivots, start=1):
            entering_v = p1_vn[p1s["pivot_col"]]
            leaving_v  = p1s["basis"][p1s["pivot_row"] - 1]
            # Show W reduced cost for the entering variable
            p1_tab = p1s.get("phase1_tab", p1s["tableau"])
            c_w = p1_tab[0, p1s["pivot_col"]]
            # Show ratio
            valid_ratios = [r for r in (p1s["ratios"] or []) if r is not None]
            min_r = min(valid_ratios) if valid_ratios else None
            if min_r is not None:
                cw_expr = rf"(\bar{{C}}^W = {_fmt(c_w)},\ \theta_{{min}} = {_fmt(min_r)})"
            else:
                cw_expr = rf"(\bar{{C}}^W = {_fmt(c_w)})"

            blocks.append(html.Div([
                dbc.Badge(f"Pha 1 — Lần lặp {p1_idx}", color="secondary",
                          pill=True, className="me-2"),
                html.Span("Biến vào: "),
                dk.DashKatex(expression=_var_label(entering_v)),
                dk.DashKatex(expression=cw_expr),
                html.Span(", Biến ra: ", className="ms-2"),
                dk.DashKatex(expression=_var_label(leaving_v)),
            ], className="d-flex align-items-center flex-wrap gap-1 mb-2 ms-2"))

        p1_end = p1_steps[-1]
        if "Vô nghiệm" in p1_end["step_name"]:
            blocks.append(dbc.Alert(
                [
                    html.Span("❌ Pha 1 kết thúc: "),
                    dk.DashKatex(expression=r"W^* \neq 0", displayMode=False),
                    html.Span(" nên bài toán vô nghiệm."),
                ],
                color="danger", className="mb-3",
            ))
            return blocks

        blocks.append(dbc.Alert(
            html.Div([
                html.Strong("\u2705 Pha 1 ho\u00e0n th\u00e0nh: "),
                dk.DashKatex(expression=r"W = 0", displayMode=False),
                html.Span(". Lo\u1ea1i b\u1ecf c\u1ed9t "),
                dk.DashKatex(expression=_art_vars_latex(art_vars)),
                html.Span(". T\u00ednh l\u1ea1i d\u00f2ng Z d\u1ef1a tr\u00ean h\u00e0m m\u1ee5c ti\u00eau g\u1ed1c."),
            ], className="d-flex align-items-center flex-wrap gap-1"),
            color="success", className="mb-3"
        ))

        blocks.append(dbc.Badge(
            "Pha 2 — Tối ưu hóa hàm mục tiêu gốc",
            color="warning", pill=True,
            className="fs-6 mb-3 px-3 py-2",
            style={"color": "#664d03"},
        ))
        if p2_steps:
            var_names = p2_steps[0].get("var_names") or var_names
    else:
        if p2_steps:
            var_names = p2_steps[0].get("var_names") or var_names

    if not p2_steps:
        return blocks

    iter_steps = [s for s in p2_steps if s["pivot_row"] is not None]

    for iter_idx, step in enumerate(iter_steps, start=1):
        var_names = step.get("var_names") or var_names
        step_pos = p2_steps.index(step)
        after    = p2_steps[step_pos + 1]

        t_before   = step["tableau"]
        t_after    = after["tableau"]
        basis      = step["basis"]
        pivot_row  = step["pivot_row"]
        pivot_col  = step["pivot_col"]
        ratios     = step["ratios"]
        non_basis  = [v for v in var_names if v not in basis]
        uid        = f"i{iter_idx}"

        iter_block: list = [
            html.Hr(className="my-4") if iter_idx > 1 else None,
            dbc.Badge(
                f"Lần lặp {iter_idx}", color="primary", pill=True,
                className="fs-6 mb-3 px-3 py-2",
            ),
        ]
        iter_block = [x for x in iter_block if x is not None]

        # Bước 1: Dạng chính tắc
        iter_block.append(_step_header(
            1, "Dạng chính tắc (Standard Form)",
            tooltip_text=(
                "Thêm biến bù không âm để chuyển ràng buộc về dạng đẳng thức. "
                "Hệ phương trình có m ẩn."
            ),
            uid=f"{uid}s1",
        ))
        iter_block.append(_math_list(format_standard_form(t_before, var_names, basis)))

        # Bước 2: Biến cơ sở / phi cơ sở
        b_labels  = ", ".join(_var_label(v) for v in basis)
        nb_labels = ", ".join(_var_label(v) for v in non_basis)
        iter_block.append(_step_header(
            2, "Phân tích biến cơ sở & phi cơ sở",
            tooltip_text=(
                "Biến cơ sở (Basic Variables): tạo nên ma trận đơn vị trong tableau. "
                "Biến phi cơ sở (Non-Basic): được đặt = 0 trong lời giải cơ sở."
            ),
            uid=f"{uid}s2",
        ))
        iter_block.append(html.Div([
            html.Span("Cơ sở B = { ", className="me-1 fst-italic"),
            dk.DashKatex(expression=b_labels),
            html.Span(" }   —   Phi cơ sở N = { ", className="mx-2 fst-italic"),
            dk.DashKatex(expression=nb_labels),
            html.Span(" }"),
        ], className="d-flex align-items-center flex-wrap gap-1 ms-2 mb-2"))

        # Bước 3: BFS hiện tại
        iter_block.append(_step_header(
            3, "Lời giải cơ sở khả thi (BFS) hiện tại",
            tooltip_text=(
                "BFS: biến phi cơ sở = 0; biến cơ sở lấy giá trị từ cột b của tableau. "
                "Z được đọc trực tiếp từ hàng 0, cột b."
            ),
            uid=f"{uid}s3",
        ))
        bfs_parts = []
        for ri, var in enumerate(basis, start=1):
            bfs_parts.append(rf"{_var_label(var)} = {_fmt(t_before[ri, -1])}")
        for var in non_basis:
            bfs_parts.append(rf"{_var_label(var)} = 0")
        z_raw = t_before[0, -1]
        if goal == "min":
            z_raw = -z_raw
        bfs_parts.append(rf"Z = {_fmt(z_raw + obj_constant)}")
        iter_block.append(_math(r", \quad ".join(bfs_parts)))

        # Bước 4: Kiểm tra tối ưu
        iter_block.append(_step_header(
            4, "Kiểm tra điều kiện tối ưu (hệ số giảm)",
            tooltip_text=(
                "Tối ưu khi mọi hệ số giảm thỏa điều kiện dừng theo quy ước nội bộ. "
                "Nếu còn hệ số giảm vi phạm, cần tiếp tục xoay."
            ),
            uid=f"{uid}s4",
        ))
        obj_row = t_before[0, :-1]
        cj_parts = [
            rf"\bar{{c}}_{{{_var_label(var_names[j])}}} = {_fmt(obj_row[j])}"
            for j in range(len(var_names))
        ]
        not_opt = any(c < -1e-10 for c in obj_row)
        iter_block.append(html.Div([
            _math(r", \quad ".join(cj_parts)),
            dbc.Badge(
                "Chưa tối ưu — cần tiếp tục" if not_opt else "Đã tối ưu",
                color="warning" if not_opt else "success",
                className="ms-1",
            ),
        ]))

        # Bước 5: Chọn biến vào / biến ra
        iter_block.append(_step_header(
            5, "Chọn biến vào & biến ra (kiểm tra tỉ số nhỏ nhất)",
            tooltip_text=(
                "Biến vào: cột có hệ số giảm vi phạm mạnh nhất. "
                "Biến ra: theo kiểm tra tỉ số nhỏ nhất, lấy hàng có tỉ số hợp lệ nhỏ nhất."
            ),
            uid=f"{uid}s5",
        ))
        ratio_parts = []
        for ri, r in enumerate(ratios):
            vl = _var_label(basis[ri])
            if r is None:
                ratio_parts.append(rf"\theta_{{{vl}}} = \infty")
            else:
                bv = t_before[ri + 1, -1]
                av = t_before[ri + 1, pivot_col]
                ratio_parts.append(
                    rf"\theta_{{{vl}}} = \frac{{{_fmt(bv)}}}{{{_fmt(av)}}} = {_fmt(r)}"
                )
        iter_block.append(_math(r", \quad ".join(ratio_parts)))
        pivot_lines = format_pivot_choice(
            pivot_row, pivot_col, var_names, basis, ratios, t_before,
        )
        for line in pivot_lines:
            iter_block.append(_math(line))

        # Bước 6: Cập nhật hệ phương trình
        iter_block.append(_step_header(
            6, "Cập nhật hệ phương trình (sau phép xoay)",
            tooltip_text=(
                "Chia hàng pivot cho phần tử chốt để chuẩn hóa về 1. "
                "Dùng phép cộng dòng để khử tất cả phần tử khác trong cột pivot về 0. "
                "Phần tử được đánh dấu là vị trí pivot."
            ),
            uid=f"{uid}s6",
        ))
        updated_eqs = format_updated_equations(
            t_after, var_names, after["basis"],
            highlight_row=pivot_row,
            highlight_col=pivot_col,
        )
        iter_block.append(_math_list(updated_eqs))

        # Bước 7: Kết luận
        if after["step_name"] == "Nghiệm tối ưu":
            t_opt = after["tableau"]
            sol_parts = [
                rf"{_var_label(v)} = {_fmt(t_opt[ri, -1])}"
                for ri, v in enumerate(after["basis"], start=1)
                if v.startswith("x")
            ]
            z_final = t_opt[0, -1]
            if goal == "min":
                z_final = -z_final
            opt_expr = r"Z^{*} = " + _fmt(z_final + obj_constant)
            if sol_parts:
                opt_expr += r", \quad " + r", \quad ".join(sol_parts)
            iter_block.append(dbc.Alert(
                [
                    html.Strong("Bước 7: ĐÃ TỐI ƯU ✅ "),
                    dk.DashKatex(expression=opt_expr),
                ],
                color="success", className="mt-3 mb-0",
            ))
        elif after["step_name"] == "Không bị chặn":
            iter_block.append(dbc.Alert(
                [
                    html.Strong("Bước 7: ❌ KHÔNG BỊ CHẶN "),
                    *_unbounded_alert_components(after, var_names, "medium"),
                ],
                color="danger", className="mt-3 mb-0",
            ))
        elif after["step_name"] == "Vô nghiệm":
            iter_block.append(dbc.Alert(
                html.Strong("❌ VÔ NGHIỆM: Hệ ràng buộc mâu thuẫn, biến thêm vào vẫn ở trong cơ sở."),
                color="danger", className="mt-3 mb-0",
            ))
        else:
            iter_block.append(html.P(
                "Bước 7: Tableau chưa tối ưu, tiếp tục lần lặp tiếp theo.",
                className="text-muted fst-italic mt-2 mb-0",
            ))

        blocks.append(html.Div(iter_block))

    # Edge cases: no pivots in Phase 2
    if not iter_steps and p2_steps:
        last_name = p2_steps[-1]["step_name"]
        if last_name in ("Không bị chặn"):
            blocks.append(dbc.Alert(
                [
                    html.Span("❌ Bài toán không bị chặn: "),
                    *_unbounded_alert_components(p2_steps[-1], var_names, "medium"),
                ],
                color="danger",
            ))
        elif last_name == "Vô nghiệm":
            blocks.append(dbc.Alert(
                "❌ Bài toán vô nghiệm — hệ ràng buộc mâu thuẫn nhau.",
                color="danger",
            ))
        else:
            t_opt   = p2_steps[-1]["tableau"]
            z_final = t_opt[0, -1]
            if goal == "min":
                z_final = -z_final
            sol_parts = [rf"Z^{{*}} = {_fmt(z_final + obj_constant)}"]
            basis_opt = p2_steps[-1]["basis"]
            for ri, v in enumerate(basis_opt, start=1):
                if v.startswith("x"):
                    sol_parts.append(rf"{_var_label(v)} = {_fmt(t_opt[ri, -1])}")
            for v in var_names[:n_dec]:
                if v not in set(basis_opt) and v.startswith("x"):
                    sol_parts.append(rf"{_var_label(v)} = 0")
            blocks.append(dbc.Alert(
                [html.Strong("Nghiệm tối ưu: "),
                 dk.DashKatex(expression=r",\quad ".join(sol_parts))],
                color="success",
            ))

    return blocks


# ── Algebra-mode renderer (new narrative style) ───────────────────────────

def render_algebra_mode(steps, var_names, goal, objective, obj_constant=0.0):
    """
    Build a narrative algebraic walk-through of the Simplex method,
    structured similarly to hand-written textbook solutions.
    """
    n_dec = len(objective)
    blocks: list = []
    m = steps[0]["tableau"].shape[0] - 1   # number of constraints

    # ── Internal helpers ──────────────────────────────────────────────────

    def _nb(basis):
        """Non-basic variable list (preserving var_names order)."""
        return [v for v in var_names if v not in basis]

    def _basis_eq(tableau, row_i, basis_var):
        """
        Return LaTeX for the equation expressing basis_var in terms of
        the remaining (non-basic) variables:
            basis_var = b  [+/- coeff * var]...
        """
        row = tableau[row_i]
        b   = row[-1]
        lhs = _var_label(basis_var)
        terms = [_fmt(b)]
        for j, v in enumerate(var_names):
            if v == basis_var:
                continue
            c = row[j]
            if abs(c) < 1e-10:
                continue
            cl = _var_label(v)
            if c > 0:                          # in the row: basis + c*v = b  →  basis = b - c*v
                coeff = _fmt(c) if c != 1 else ""
                terms.append(f"- {coeff}{cl}")
            else:                              # c < 0  →  basis = b + |c|*v
                coeff = _fmt(abs(c)) if abs(c) != 1 else ""
                terms.append(f"+ {coeff}{cl}")
        result = lhs + " = " + " ".join(terms)
        return result

    def _z_from_tableau(tableau, basis, goal):
        """
        Return LaTeX for Z expressed in terms of the current non-basic
        variables using reduced costs stored in tableau row 0.

        For min:  display coeff of x_j  =  tableau[0, j]
        For max:  display coeff of x_j  = -tableau[0, j]
        """
        z_raw = tableau[0, -1]
        z_val = (-z_raw + obj_constant) if goal == "min" else (z_raw + obj_constant)
        nb    = _nb(basis)
        parts = [_fmt(z_val)]
        for j, v in enumerate(var_names):
            if v not in nb:
                continue
            c  = tableau[0, j] if goal == "min" else -tableau[0, j]
            if abs(c) < 1e-10:
                continue
            cl = _var_label(v)
            if c > 0:
                coeff = _fmt(c) if c != 1 else ""
                parts.append(f"+ {coeff}{cl}")
            else:
                coeff = _fmt(abs(c)) if abs(c) != 1 else ""
                parts.append(f"- {coeff}{cl}")
        return "Z = " + " ".join(parts)

    def _w_expression(phase1_tab, basis):
        """
        Return LaTeX for W expressed in terms of non-basic variables.
        W = -phase1_tab[0, -1] + Σ phase1_tab[0, j] * xⱼ  for j ∈ NB
        """
        row   = phase1_tab[0]
        w_val = -row[-1]
        nb    = _nb(basis)
        parts = [_fmt(w_val)]
        for j, v in enumerate(var_names):
            if v not in nb:
                continue
            c = row[j]
            if abs(c) < 1e-10:
                continue
            cl = _var_label(v)
            if c > 0:
                coeff = _fmt(c) if c != 1 else ""
                parts.append(f"+ {coeff}{cl}")
            else:
                coeff = _fmt(abs(c)) if abs(c) != 1 else ""
                parts.append(f"- {coeff}{cl}")
        return "W = " + " ".join(parts)

    def _eq_lbl(eq_num, primes):
        """Return label like (1), (1'), (1'') for a constraint equation."""
        return f"({eq_num}{chr(39) * primes})"

    def _show_system(tableau, basis, primes):
        """Render the system of basis-variable equations with labels."""
        items = []
        for i in range(1, m + 1):
            eq  = _basis_eq(tableau, i, basis[i - 1])
            lbl = _eq_lbl(i, primes)
            items.append(html.Div([
                dk.DashKatex(expression=eq),
                html.Span(f"  {lbl}", className="text-muted small ms-3"),
            ], className="d-flex align-items-center mb-1 ms-3 gap-1"))
        return items

    def _show_bfs(tableau, basis, goal):
        """Render the current basic feasible solution as a KaTeX block."""
        nb    = _nb(basis)
        z_raw = tableau[0, -1]
        z_val = (-z_raw + obj_constant) if goal == "min" else (z_raw + obj_constant)
        parts = []
        for v in nb:
            parts.append(rf"{_var_label(v)} = 0")
        for i, v in enumerate(basis, start=1):
            parts.append(rf"{_var_label(v)} = {_fmt(tableau[i, -1])}")
        parts.append(rf"Z = {_fmt(z_val)}")
        return _math(r"\quad ".join(parts))

    def _optimality_check(tableau, basis, primes, goal):
        """
        Build component list for the optimality-check subsection:
          • Rút cơ sở: each basis variable expressed in non-basics
          • Thế vào Z: Z written in terms of non-basics (from row 0)
          • C̄_j values with analysis
        Returns (component_list, not_optimal_vars) where
        not_optimal_vars is a list of (coeff, var_name) that violate optimality.
        """
        items = []
        nb    = _nb(basis)

        # Rút cơ sở
        items.append(html.Div(
            "+ Rút cơ sở theo biến không cơ sở:",
            className="fw-semibold ms-2 mb-1 mt-2",
        ))
        for i in range(1, m + 1):
            eq  = _basis_eq(tableau, i, basis[i - 1])
            lbl = _eq_lbl(i, primes)
            items.append(html.Div([
                html.Span(f"Từ {lbl}:", className="text-muted small"),
                dk.DashKatex(expression=eq),
            ], className="d-flex align-items-center flex-wrap mb-1 ms-4 gap-2"))

        # Thế vào Z
        items.append(html.Div("Thế vào Z:", className="fw-semibold ms-2 mt-2 mb-1"))
        items.append(_math(_z_from_tableau(tableau, basis, goal)))

        # C̄_j analysis
        cj_parts       = []
        not_opt_vars   = []
        for j, v in enumerate(var_names):
            if v not in nb:
                continue
            c  = tableau[0, j] if goal == "min" else -tableau[0, j]
            cl = _var_label(v)
            cj_parts.append(rf"\bar{{C}}_{{{cl}}} = {_fmt(c)}")
            if (goal == "min" and c < -1e-10) or (goal == "max" and c > 1e-10):
                not_opt_vars.append((c, v))

        if cj_parts:
            items.append(_math(r"\quad ".join(cj_parts)))

        return items, not_opt_vars

    # ── Objective header ──────────────────────────────────────────────────
    obj_latex = format_objective(objective, var_names[:n_dec], goal)
    if obj_constant:
        abs_c = abs(obj_constant)
        c_str = str(int(abs_c)) if abs_c == int(abs_c) else f"{abs_c:g}"
        sign  = "+" if obj_constant > 0 else "-"
        obj_latex += rf" {sign} {c_str}"
    blocks.append(dbc.Alert(
        [html.Strong("Hàm mục tiêu: "), dk.DashKatex(expression=obj_latex)],
        color="info", className="mb-3",
    ))

    # ── Split Phase 1 / Phase 2 ──────────────────────────────────────────
    p1_steps = [s for s in steps if s.get("phase") == 1]
    p2_steps = [s for s in steps if s.get("phase", 2) == 2]
    sec    = 1   # section counter
    primes = 0   # equation-label prime counter

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 1  (detailed algebraic rendering)
    # ══════════════════════════════════════════════════════════════════════
    if p1_steps:
        p1_vn     = p1_steps[0].get("var_names") or var_names
        var_names = p1_vn  # switch closure to Phase-1 variable names
        art_vars  = _phase1_artificial_vars(p1_steps[0], p1_vn)
        p1t0      = p1_steps[0].get("phase1_tab", p1_steps[0]["tableau"])
        m_p1      = p1t0.shape[0] - 1

        # ── Phase 1 header ────────────────────────────────────────────────
        blocks.append(dbc.Badge(
            "Pha 1 — Tìm lời giải cơ sở khả thi (BFS)",
            color="warning", pill=True,
            className="fs-6 mb-3 px-3 py-2",
            style={"color": "#664d03"},
        ))
        blocks.append(dbc.Alert([
            html.Div([
            html.Span(
                "Ràng buộc dạng '=' hoặc lớn hơn hoặc bằng không có biến bù tự nhiên, cần thêm biến nhân tạo. "
                "Pha 1 tối thiểu hóa hàm mục tiêu nhân tạo: ",
                className="me-2",
            ),
            dk.DashKatex(expression=format_w_objective(art_vars), displayMode=False),
            html.Span(" để tìm BFS cho Pha 2.", className="ms-2"),
            ], className="d-flex align-items-center flex-wrap gap-1"),
        ], color="warning", className="mb-3"))

        # ── Setup: artificial objective ───────────────────────────────────
        blocks.append(html.Div(
            f"{sec}) Định nghĩa hàm mục tiêu nhân tạo:",
            className="fw-bold text-primary mt-2 mb-2",
        ))
        sec += 1
        w_obj_latex = format_w_objective(art_vars)
        blocks.append(_math(w_obj_latex))

        # ── Initial Phase 1 system ────────────────────────────────────────
        b0_p1  = p1_steps[0]["basis"]
        nb0_p1 = _nb(b0_p1)

        blocks.append(html.Div(
            f"{sec}) Hệ phương trình ban đầu (Pha 1):",
            className="fw-bold text-primary mt-2 mb-2",
        ))
        sec += 1

        b_labels_p1  = ", ".join(_var_label(v) for v in b0_p1)
        nb_labels_p1 = ", ".join(_var_label(v) for v in nb0_p1)
        blocks.append(html.Div([
            html.Span("+ Biến cơ sở: ", className="fw-semibold"),
            dk.DashKatex(expression=b_labels_p1),
        ], className="ms-2 mb-1 d-flex align-items-center gap-1"))
        blocks.append(html.Div([
            html.Span("+ Biến không cơ sở: ", className="fw-semibold"),
            dk.DashKatex(expression=nb_labels_p1),
        ], className="ms-2 mb-1 d-flex align-items-center gap-1"))

        blocks.extend(_show_system(p1t0, b0_p1, primes))

        # W expression
        w_expr_init = _w_expression(p1t0, b0_p1)
        blocks.append(html.Div(
            "+ Biểu diễn W theo biến phi cơ sở:",
            className="fw-semibold ms-2 mt-2 mb-1",
        ))
        blocks.append(_math(w_expr_init))

        # BFS
        w_val_init = -p1t0[0, -1]
        bfs_parts_p1 = []
        for v in nb0_p1:
            bfs_parts_p1.append(rf"{_var_label(v)} = 0")
        for i, v in enumerate(b0_p1, start=1):
            bfs_parts_p1.append(rf"{_var_label(v)} = {_fmt(p1t0[i, -1])}")
        bfs_parts_p1.append(rf"W = {_fmt(w_val_init)}")
        blocks.append(html.Div(
            "+ Lời giải cơ sở ban đầu:",
            className="fw-semibold ms-2 mt-1 mb-1",
        ))
        blocks.append(_math(r"\quad ".join(bfs_parts_p1)))

        # ── Phase 1 iterations ────────────────────────────────────────────
        p1_pivots = [s for s in p1_steps if s["pivot_row"] is not None]
        for p1_idx, step_p1 in enumerate(p1_pivots):
            step_pos_p1   = p1_steps.index(step_p1)
            after_p1      = p1_steps[step_pos_p1 + 1]
            p1_tab_before = step_p1.get("phase1_tab", step_p1["tableau"])
            basis_bef_p1  = step_p1["basis"]
            pivot_row_p1  = step_p1["pivot_row"]
            pivot_col_p1  = step_p1["pivot_col"]
            ratios_p1     = step_p1["ratios"]
            entering_p1   = var_names[pivot_col_p1]
            leaving_p1    = basis_bef_p1[pivot_row_p1 - 1]
            nb_bef_p1     = _nb(basis_bef_p1)

            # W optimality check
            blocks.append(html.Hr(className="my-3"))
            blocks.append(html.Div(
                "Kiểm tra W đã tối thiểu chưa?",
                className="fw-bold text-secondary mb-2",
            ))
            w_cj_parts = []
            w_not_opt  = []
            for j, v in enumerate(var_names):
                if v not in nb_bef_p1:
                    continue
                c_w = p1_tab_before[0, j]
                cl  = _var_label(v)
                w_cj_parts.append(rf"\bar{{C}}^W_{{{cl}}} = {_fmt(c_w)}")
                if c_w < -1e-10:
                    w_not_opt.append((c_w, v))
            if w_cj_parts:
                blocks.append(_math(r"\quad ".join(w_cj_parts)))
            if w_not_opt:
                worst_c_w, worst_v_w = min(w_not_opt, key=lambda x: x[0])
                cl_w = _var_label(worst_v_w)
                blocks.append(html.Div([
                    dk.DashKatex(expression=rf"\bar{{C}}^W_{{{cl_w}}} = {_fmt(worst_c_w)} < 0"),
                    html.Span(" nên W chưa tối thiểu, cần tiếp tục.", className="ms-2"),
                ], className="ms-4 mb-1 d-flex align-items-center flex-wrap"))

            # Pivot selection
            blocks.append(html.Hr(className="my-3"))
            blocks.append(html.Div(
                f"{sec}) Pha 1 — Lần lặp {p1_idx + 1}: Chọn biến cơ sở mới:",
                className="fw-bold text-primary mb-2",
            ))
            sec += 1

            entering_lbl_p1 = _var_label(entering_p1)
            leaving_lbl_p1  = _var_label(leaving_p1)
            c_enter_w       = p1_tab_before[0, pivot_col_p1]

            blocks.append(html.Div([
                html.Span("+ ", className="ms-2"),
                dk.DashKatex(expression=entering_lbl_p1),
                html.Span(" là biến vào với ", className="ms-1"),
                _hover_term(
                    "hệ số giảm",
                    "Hệ số giảm Cbar_j đo mức thay đổi hàm mục tiêu khi tăng biến không cơ sở x_j từ 0.",
                    f"rc-p1-{p1_idx + 1}",
                ),
                dk.DashKatex(expression=rf"\bar{{C}}^W = {_fmt(c_enter_w)}", displayMode=False),
                html.Span(" (nhỏ nhất).", className="ms-1"),
            ], className="d-flex align-items-center flex-wrap gap-1 mb-2"))

            blocks.append(html.Div(
                "+ Chọn biến ra (min ratio test):",
                className="fw-semibold ms-2 mb-1",
            ))
            for i_p1 in range(m_p1):
                a_p1   = p1_tab_before[i_p1 + 1, pivot_col_p1]
                b_v_p1 = p1_tab_before[i_p1 + 1, -1]
                bv_p1  = basis_bef_p1[i_p1]
                eq_lbl_p1 = _eq_lbl(i_p1 + 1, primes)
                eq_str_p1 = _basis_eq(p1_tab_before, i_p1 + 1, bv_p1)
                if abs(a_p1) < 1e-10:
                    note_p1 = html.Span(
                        "(hệ số bằng 0, bỏ qua)",
                        className="text-muted ms-2 small fst-italic",
                    )
                elif a_p1 < 0:
                    note_p1 = html.Span(
                        "(hệ số âm, không ràng buộc)",
                        className="text-muted ms-2 small fst-italic",
                    )
                else:
                    ratio_p1    = b_v_p1 / a_p1
                    is_pivot_p1 = (i_p1 + 1 == pivot_row_p1)
                    note_p1 = html.Span([
                        dk.DashKatex(
                            expression=rf"\theta = \frac{{{_fmt(b_v_p1)}}}{{{_fmt(a_p1)}}} = {_fmt(ratio_p1)}",
                            displayMode=False,
                        ),
                        html.Span(" ← chọn",
                                  className="text-success fw-bold ms-1")
                        if is_pivot_p1 else html.Span(""),
                    ], className="text-success fw-semibold ms-2 small"
                       if is_pivot_p1 else "text-muted ms-2 small")
                blocks.append(html.Div([
                    html.Span(f"Từ {eq_lbl_p1}:", className="text-muted small"),
                    dk.DashKatex(expression=eq_str_p1),
                    note_p1,
                ], className="ms-4 mb-1 d-flex align-items-center flex-wrap gap-2"))

            blocks.append(html.Div([
                html.Span("Chọn ", className="ms-2"),
                dk.DashKatex(expression=leaving_lbl_p1),
                html.Span(" là biến ra.", className="ms-1"),
            ], className="fw-semibold text-primary"
               " d-flex align-items-center flex-wrap gap-2 mb-1"))

            # New system after pivot
            primes += 1
            p1_tab_next    = after_p1.get("phase1_tab")
            basis_aft_p1   = after_p1["basis"]
            nb_aft_p1      = _nb(basis_aft_p1)

            blocks.append(html.Hr(className="my-3"))
            blocks.append(html.Div(
                f"{sec}) Hệ phương trình mới"
                f" (đưa {entering_p1} vào, đưa {leaving_p1} ra):",
                className="fw-bold text-primary mb-2",
            ))
            sec += 1

            if p1_tab_next is not None:
                blocks.extend(_show_system(p1_tab_next, basis_aft_p1, primes))
                b_new_lbl_p1  = ", ".join(_var_label(v) for v in basis_aft_p1)
                nb_new_lbl_p1 = ", ".join(_var_label(v) for v in nb_aft_p1)
                blocks.append(html.Div([
                    html.Span("+ Biến cơ sở: ", className="fw-semibold"),
                    dk.DashKatex(expression=b_new_lbl_p1),
                ], className="ms-2 mb-1 mt-2 d-flex align-items-center gap-1"))
                blocks.append(html.Div([
                    html.Span("+ Biến không cơ sở: ", className="fw-semibold"),
                    dk.DashKatex(expression=nb_new_lbl_p1),
                ], className="ms-2 mb-1 d-flex align-items-center gap-1"))
                w_expr_new = _w_expression(p1_tab_next, basis_aft_p1)
                blocks.append(_math(w_expr_new))
                w_val_new = -p1_tab_next[0, -1]
                bfs_new = []
                for v in nb_aft_p1:
                    bfs_new.append(rf"{_var_label(v)} = 0")
                for i, v in enumerate(basis_aft_p1, start=1):
                    bfs_new.append(rf"{_var_label(v)} = {_fmt(p1_tab_next[i, -1])}")
                bfs_new.append(rf"W = {_fmt(w_val_new)}")
                blocks.append(html.Div(
                    "+ Lời giải cơ sở mới:",
                    className="fw-semibold ms-2 mt-1 mb-1",
                ))
                blocks.append(_math(r"\quad ".join(bfs_new)))

        # ── Phase 1 conclusion ────────────────────────────────────────────
        p1_end = p1_steps[-1]
        if "Vô nghiệm" in p1_end["step_name"]:
            blocks.append(html.Hr(className="my-3"))
            blocks.append(dbc.Alert(
                [
                    html.Span("❌ Pha 1 kết thúc: "),
                    dk.DashKatex(expression=r"W^* \neq 0", displayMode=False),
                    html.Span(" nên bài toán vô nghiệm."),
                ],
                color="danger", className="mb-3",
            ))
            return blocks

        # Final W optimality check (if last step is the conclusion, not a pivot)
        p1_final_tab = p1_end.get("phase1_tab")
        if p1_final_tab is not None and p1_end["pivot_row"] is None:
            basis_final_p1 = p1_end["basis"]
            nb_final_p1    = _nb(basis_final_p1)
            blocks.append(html.Hr(className="my-3"))
            blocks.append(html.Div(
                "Kiểm tra W đã tối thiểu chưa?",
                className="fw-bold text-secondary mb-2",
            ))
            w_cj_final = []
            for j, v in enumerate(var_names):
                if v not in nb_final_p1:
                    continue
                c_w = p1_final_tab[0, j]
                cl  = _var_label(v)
                w_cj_final.append(rf"\bar{{C}}^W_{{{cl}}} = {_fmt(c_w)}")
            if w_cj_final:
                blocks.append(_math(r"\quad ".join(w_cj_final)))
            w_final = -p1_final_tab[0, -1]
            blocks.append(html.Div([
                html.Span("Tất cả ", className="ms-2 me-1"),
                dk.DashKatex(expression=r"\bar{C}^W_j \geq 0", displayMode=False),
                html.Span(" và ", className="ms-1"),
                dk.DashKatex(expression=rf"W = {_fmt(w_final)} = 0", displayMode=False),
                html.Span(" nên ", className="ms-1"),
                html.Span("BFS khả thi đã tìm được.",
                          className="fw-bold text-success"),
            ], className="d-flex align-items-center flex-wrap gap-1 mb-2"))

        blocks.append(dbc.Alert(
            html.Div([
                html.Strong("Pha 1 hoàn thành. "),
                html.Span("Loại bỏ các biến thêm vào ("),
                dk.DashKatex(expression=_art_vars_latex(art_vars)),
                html.Span(") khỏi hệ phương trình. Chuyển sang Pha 2."),
            ], className="d-flex align-items-center flex-wrap gap-1"),
            color="success", className="mb-3"
        ))

        # ── Phase 1 → Phase 2 Transition ─────────────────────────────────
        if p2_steps:
            var_names = p2_steps[0].get("var_names") or var_names

        blocks.append(dbc.Badge(
            "Pha 2 — Tối ưu hóa hàm mục tiêu gốc",
            color="warning", pill=True,
            className="fs-6 mb-3 px-3 py-2",
            style={"color": "#664d03"},
        ))

        blocks.append(html.Div(
            f"{sec}) Chuyển sang Pha 2 — Khôi phục hàm mục tiêu gốc:",
            className="fw-bold text-primary mt-2 mb-2",
        ))
        sec += 1
        obj_latex_z = format_objective(
            objective, [f"x{j+1}" for j in range(n_dec)], goal,
        )
        if obj_constant:
            abs_c = abs(obj_constant)
            c_str = str(int(abs_c)) if abs_c == int(abs_c) else f"{abs_c:g}"
            sign  = "+" if obj_constant > 0 else "-"
            obj_latex_z += rf" {sign} {c_str}"
        blocks.append(html.Div([
            html.Span("+ Hàm mục tiêu gốc: ", className="fw-semibold"),
            dk.DashKatex(expression=obj_latex_z),
        ], className="ms-2 mb-2 d-flex align-items-center gap-1"))

        if p2_steps:
            t0_p2 = p2_steps[0]["tableau"]
            b0_p2 = p2_steps[0]["basis"]
            blocks.append(html.Div(
                "+ Thế các biến cơ sở (từ hệ pt cuối Pha 1) vào Z:",
                className="fw-semibold ms-2 mb-1",
            ))
            for i_t, bv_t in enumerate(b0_p2):
                if bv_t.startswith("x"):
                    eq_t = _basis_eq(t0_p2, i_t + 1, bv_t)
                    blocks.append(html.Div([
                        html.Span("  Từ hệ pt Pha 1: ",
                                  className="text-muted small"),
                        dk.DashKatex(expression=eq_t),
                    ], className="ms-4 mb-1 d-flex align-items-center"
                       " flex-wrap gap-2"))
            z_expr_p2 = _z_from_tableau(t0_p2, b0_p2, goal)
            blocks.append(html.Div(
                "+ Sau khi thế:",
                className="fw-semibold ms-2 mt-2 mb-1",
            ))
            blocks.append(_math(z_expr_p2))

    else:
        # No Phase 1 — proceed directly
        if p2_steps:
            var_names = p2_steps[0].get("var_names") or var_names

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 2  (or the only phase if no artificials were needed)
    # ══════════════════════════════════════════════════════════════════════
    iter_steps = [s for s in p2_steps if s["pivot_row"] is not None]

    # ── Initial Phase 2 system + BFS ─────────────────────────────────────
    t0  = p2_steps[0]["tableau"]
    b0  = p2_steps[0]["basis"]
    nb0 = _nb(b0)

    blocks.append(html.Div(
        f"{sec}) Hệ phương trình dạng chính tắc (Pha 2):"
        if p1_steps
        else f"{sec}) Chuyển hệ phương trình về dạng chính tắc:",
        className="fw-bold text-primary mt-2 mb-2",
    ))
    sec += 1
    blocks.extend(_show_system(t0, b0, primes))

    b_labels  = ", ".join(_var_label(v) for v in b0)
    nb_labels = ", ".join(_var_label(v) for v in nb0)
    blocks.append(html.Div([
        html.Span("+ Biến cơ sở: ", className="fw-semibold"),
        dk.DashKatex(expression=b_labels),
    ], className="ms-2 mb-1 mt-2 d-flex align-items-center gap-1"))
    blocks.append(html.Div([
        html.Span("+ Biến không cơ sở: ", className="fw-semibold"),
        dk.DashKatex(expression=nb_labels),
    ], className="ms-2 mb-1 d-flex align-items-center gap-1"))

    blocks.append(html.Div(
        "+ Lời giải cơ sở ban đầu (biến phi cơ sở = 0):",
        className="fw-semibold ms-2 mt-1 mb-1",
    ))
    blocks.append(_show_bfs(t0, b0, goal))

    # ── Handle: already optimal at initial BFS (no pivots needed) ────────
    if not iter_steps:
        terminal = p2_steps[-1]
        t_term   = terminal["tableau"]
        b_term   = terminal["basis"]
        z_term   = (-t_term[0, -1] + obj_constant) if goal == "min" else (t_term[0, -1] + obj_constant)

        blocks.append(html.Hr(className="my-3"))
        blocks.append(html.Div(
            "Kiểm tra xem tối ưu chưa?",
            className="fw-bold text-secondary mb-2",
        ))

        if terminal["step_name"] == "Nghiệm tối ưu":
            opt_items, _ = _optimality_check(t_term, b_term, primes, goal)
            blocks.extend(opt_items)
            cmp_expr = r"\bar{C}_j \geq 0" if goal == "min" else r"\bar{C}_j \leq 0"
            blocks.append(html.Div([
                html.Span("Tất cả ", className="ms-2 me-1"),
                dk.DashKatex(expression=cmp_expr, displayMode=False),
                html.Span(" nên lời giải ban đầu đã là tối ưu.", className="ms-1"),
            ], className="text-success fw-semibold mt-1 d-flex align-items-center flex-wrap"))
            blocks.append(html.Hr(className="my-3"))
            sol_parts = [rf"Z^* = {_fmt(z_term)}"]
            for ri, v in enumerate(b_term, start=1):
                if v.startswith("x"):
                    sol_parts.append(rf"{_var_label(v)} = {_fmt(t_term[ri, -1])}")
            for v in var_names[:n_dec]:
                if v not in set(b_term) and v.startswith("x"):
                    sol_parts.append(rf"{_var_label(v)} = 0")
            blocks.append(dbc.Alert(
                [html.Strong("Vậy: "), dk.DashKatex(expression=r",\quad ".join(sol_parts))],
                color="success", className="mt-2",
            ))
        elif terminal["step_name"] == "Không bị chặn":
            blocks.append(dbc.Alert(
                [
                    html.Span("❌ Bài toán không bị chặn: "),
                    *_unbounded_alert_components(terminal, var_names, "full"),
                ],
                color="danger",
            ))
        elif terminal["step_name"] == "Vô nghiệm":
            blocks.append(dbc.Alert(
                "❌ Bài toán vô nghiệm — hệ ràng buộc mâu thuẫn nhau.",
                color="danger",
            ))
        return blocks

    # ── Iterate through each pivot ────────────────────────────────────────
    for iter_idx, step in enumerate(iter_steps, start=1):
        var_names = step.get("var_names") or var_names
        step_pos   = p2_steps.index(step)
        after      = p2_steps[step_pos + 1]

        t_before   = step["tableau"]
        t_after    = after["tableau"]
        basis      = step["basis"]
        pivot_row  = step["pivot_row"]
        pivot_col  = step["pivot_col"]
        ratios     = step["ratios"]
        entering  = var_names[pivot_col]
        leaving   = basis[pivot_row - 1]
        new_basis = after["basis"]
        nb_after  = _nb(new_basis)

        # ── Kiểm tra tối ưu trước phép xoay ──────────────────────────────
        blocks.append(html.Hr(className="my-3"))
        blocks.append(html.Div(
            "Kiểm tra xem tối ưu chưa?",
            className="fw-bold text-secondary mb-2",
        ))

        opt_items, not_opt_vars = _optimality_check(t_before, basis, primes, goal)
        blocks.extend(opt_items)

        # Conclusion: pick the most-violating Cj and state result
        if not_opt_vars:
            worst_c, worst_v = (
                min(not_opt_vars, key=lambda x: x[0]) if goal == "min"
                else max(not_opt_vars, key=lambda x: x[0])
            )
            cl      = _var_label(worst_v)
            compare = "< 0" if goal == "min" else "> 0"
            blocks.append(html.Div([
                dk.DashKatex(expression=rf"\bar{{C}}_{{{cl}}} = {_fmt(worst_c)} {compare}"),
                html.Span(" nên bài toán chưa tối ưu, cần thực hiện thêm bước xoay.",
                          className="ms-2"),
            ], className="ms-4 mb-1 d-flex align-items-center flex-wrap"))

        # ── Chọn biến vào / biến ra ───────────────────────────────────────
        blocks.append(html.Hr(className="my-3"))
        blocks.append(html.Div(
            f"{sec}) Chọn biến cơ sở mới:",
            className="fw-bold text-primary mb-2",
        ))
        sec += 1

        entering_label = _var_label(entering)
        leaving_label  = _var_label(leaving)
        c_enter = t_before[0, pivot_col] if goal == "min" else -t_before[0, pivot_col]
        sign_word = "âm nhất" if goal == "min" else "dương nhất"

        blocks.append(html.Div([
            html.Span("+", className="ms-2"),
            dk.DashKatex(expression=entering_label, displayMode=False),
            html.Span("là biến cơ sở mới với"),
            _hover_term(
                "hệ số giảm",
                "Hệ số giảm Cbar_j đo mức thay đổi hàm mục tiêu khi tăng biến không cơ sở x_j từ 0.",
                f"rc-p2-{iter_idx}",
            ),
            dk.DashKatex(expression=rf"\bar{{C}} = {_fmt(c_enter)}", displayMode=False),
            html.Span(f"({sign_word} trong các biến không cơ sở)."),
        ], className="d-flex align-items-center flex-wrap gap-1 mb-2"))

        blocks.append(html.Div(
            "+ Chọn biến từ cơ sở chuyển sang không cơ sở (min ratio test):",
            className="fw-semibold ms-2 mb-1",
        ))

        for i in range(m):
            a     = t_before[i + 1, pivot_col]
            b_val = t_before[i + 1, -1]
            bv    = basis[i]
            eq_lbl = _eq_lbl(i + 1, primes)
            eq_str = _basis_eq(t_before, i + 1, bv)

            if abs(a) < 1e-10:
                note = html.Span("(hệ số bằng 0, bỏ qua)", className="text-muted ms-2 small fst-italic")
            elif a < 0:
                note = html.Span(
                    f"(tăng {entering} làm {bv} tăng, không ràng buộc)",
                    className="text-muted ms-2 small fst-italic",
                )
            else:
                ratio    = b_val / a
                is_pivot = (i + 1 == pivot_row)
                note = html.Span([
                    dk.DashKatex(
                        expression=rf"\theta = \frac{{{_fmt(b_val)}}}{{{_fmt(a)}}} = {_fmt(ratio)}",
                        displayMode=False,
                    ),
                    html.Span(" ← chọn", className="text-success fw-bold ms-1") if is_pivot else html.Span(""),
                ], className="text-success fw-semibold ms-2 small" if is_pivot else "text-muted ms-2 small")

                blocks.append(html.Div([
                html.Span(f"Từ {eq_lbl}:", className="text-muted small"),
                dk.DashKatex(expression=eq_str, displayMode=False),
                note,
            ], className="ms-4 mb-1 d-flex align-items-center flex-wrap gap-2"))

        blocks.append(html.Div([
            html.Span("Ta chọn ", className="ms-2"),
            dk.DashKatex(expression=leaving_label),
            html.Span(" là biến không cơ sở mới. Viết lại hệ phương trình chính tắc.", className="ms-1"),
        ], className="fw-semibold text-primary d-flex align-items-center flex-wrap gap-2 mb-1"))

        # ── Hệ phương trình mới sau phép xoay ────────────────────────────
        primes += 1
        z_after_raw = t_after[0, -1]
        z_after     = (-z_after_raw + obj_constant) if goal == "min" else (z_after_raw + obj_constant)

        blocks.append(html.Hr(className="my-3"))
        blocks.append(html.Div(
            f"{sec}) Hệ phương trình mới"
            f" (đưa {entering} vào cơ sở, đưa {leaving} ra khỏi cơ sở):",
            className="fw-bold text-primary mb-2",
        ))
        sec += 1
        blocks.extend(_show_system(t_after, new_basis, primes))

        b_new_labels  = ", ".join(_var_label(v) for v in new_basis)
        nb_new_labels = ", ".join(_var_label(v) for v in nb_after)
        blocks.append(html.Div([
            html.Span("+ Biến cơ sở mới: ", className="fw-semibold"),
            dk.DashKatex(expression=b_new_labels),
        ], className="ms-2 mb-1 mt-2 d-flex align-items-center gap-1"))
        blocks.append(html.Div([
            html.Span("+ Biến không cơ sở mới: ", className="fw-semibold"),
            dk.DashKatex(expression=nb_new_labels),
        ], className="ms-2 mb-1 d-flex align-items-center gap-1"))
        blocks.append(html.Div(
            "+ Lời giải cơ sở mới (biến phi cơ sở = 0):",
            className="fw-semibold ms-2 mt-1 mb-1",
        ))
        blocks.append(_show_bfs(t_after, new_basis, goal))

        # ── If last iteration: final optimality check + conclusion ────────
        if after["step_name"] == "Nghiệm tối ưu":
            blocks.append(html.Hr(className="my-3"))
            blocks.append(html.Div(
                "Kiểm tra lời giải tối ưu chưa?",
                className="fw-bold text-secondary mb-2",
            ))

            opt_items_f, _ = _optimality_check(t_after, new_basis, primes, goal)
            blocks.extend(opt_items_f)

            # Build reduced-cost summary line
            for j, v in enumerate(var_names):
                if v not in nb_after:
                    continue
                c  = t_after[0, j] if goal == "min" else -t_after[0, j]
                cl = _var_label(v)
            cmp_expr = r"\bar{C}_j \geq 0" if goal == "min" else r"\bar{C}_j \leq 0"
            blocks.append(html.Div([
                html.Span("Tất cả ", className="ms-2 me-1"),
                dk.DashKatex(expression=cmp_expr, displayMode=False),
                html.Span(" nên lời giải hiện tại là tối ưu.", className="ms-1"),
            ], className="text-success fw-semibold mt-1 d-flex align-items-center flex-wrap"))

            # Final answer
            blocks.append(html.Hr(className="my-3"))
            sol_parts = [rf"Z^* = {_fmt(z_after)}"]
            basis_set = set(new_basis)
            for ri, v in enumerate(new_basis, start=1):
                if v.startswith("x"):
                    sol_parts.append(rf"{_var_label(v)} = {_fmt(t_after[ri, -1])}")
            for v in var_names[:n_dec]:
                if v not in basis_set and v.startswith("x"):
                    sol_parts.append(rf"{_var_label(v)} = 0")
            blocks.append(dbc.Alert(
                [html.Strong("Vậy: "), dk.DashKatex(expression=r",\quad ".join(sol_parts))],
                color="success", className="mt-2",
            ))

        elif after["step_name"] == "Không bị chặn":
            blocks.append(dbc.Alert(
                [
                    html.Strong("❌ Không bị chặn: "),
                    *_unbounded_alert_components(after, var_names, "full"),
                ],
                color="danger", className="mt-3",
            ))
        elif after["step_name"] == "Vô nghiệm":
            blocks.append(dbc.Alert(
                html.Strong("❌ VÔ NGHIỆM: Hệ ràng buộc mâu thuẫn, biến thêm vào vẫn ở trong cơ sở."),
                color="danger", className="mt-3",
            ))

    return blocks


# ── Serialisation helpers ─────────────────────────────────────────────────

def _serialize_steps(steps, var_names, goal, objective, obj_constant=0.0):
    """Convert solve_steps() output (which contains np.ndarray) to JSON-safe dict."""
    serialized = []
    for s in steps:
        sd = {
            "step_name":   s["step_name"],
            "tableau":     s["tableau"].tolist(),
            "basis":       s["basis"],
            "pivot_row":   s["pivot_row"],
            "pivot_col":   s["pivot_col"],
            "ratios":      s["ratios"],
            "explanation": s["explanation"],
            "var_names":   s.get("var_names"),
            "phase":       s.get("phase", 2),
        }
        if "phase1_tab" in s:
            sd["phase1_tab"] = s["phase1_tab"].tolist()
        if "art_vars" in s:
            sd["art_vars"] = s["art_vars"]
        serialized.append(sd)
    return {
        "steps":       serialized,
        "var_names":   var_names,
        "goal":        goal,
        "objective":   objective,
        "obj_constant": float(obj_constant) if obj_constant is not None else 0.0,
        "error":       None,
    }


def _deserialize_steps(serialized_steps):
    """Restore np.ndarray tableau from serialized step dicts."""
    result = []
    for s in serialized_steps:
        d = {**s, "tableau": np.array(s["tableau"])}
        if "phase1_tab" in s and s["phase1_tab"] is not None:
            d["phase1_tab"] = np.array(s["phase1_tab"])
        result.append(d)
    return result


# ── Callback 1: Generate input form on n / m change ───────────────────────

@callback(
    Output("objective-inputs",  "children"),
    Output("variable-sign-inputs", "children"),
    Output("constraint-inputs", "children"),
    Input("num-vars",        "value"),
    Input("num-constraints", "value"),
)
def generate_inputs(n_vars, n_constraints):
    n = max(1, min(UI_MAX_DIM, int(n_vars)        if n_vars        is not None else 2))
    m = max(1, min(UI_MAX_DIM, int(n_constraints) if n_constraints is not None else 2))

    # ── Objective coefficient inputs ──────────────────────────────────────
    obj_parts = []
    for j in range(n):
        obj_parts.append(dbc.InputGroup([
            dbc.Input(
                id={"type": "obj-coeff", "index": j},
                type="text", inputMode="decimal", placeholder=f"c{_sub(j+1)}",
                style={"width": "72px"}, size="sm",
            ),
            dbc.InputGroupText(_xsub(j+1), className="lp-math-affix"),
            *([] if j == n - 1 else [dbc.InputGroupText("+")]),
        ], className="me-1 mb-1"))

    # ── Variable sign selectors ───────────────────────────────────────────
    sign_parts = []
    for j in range(n):
        sign_parts.append(
            dbc.InputGroup([
                dbc.InputGroupText(_xsub(j + 1), className="lp-math-affix"),
                dbc.Select(
                    id={"type": "var-sign", "index": j},
                    options=[
                        {"label": f"x{_sub(j+1)} ≥ 0", "value": "nonnegative"},
                        {"label": f"x{_sub(j+1)} ∈ ℝ", "value": "free"},
                    ],
                    value="nonnegative",
                    size="sm",
                    style={"width": "145px"},
                    className="lp-math-select",
                ),
            ], className="me-1 mb-1")
        )

    # ── Constraint rows ───────────────────────────────────────────────────
    # Coefficient indices: flat row-major → con_coeff_vals[i*n + j] in solve cb
    con_rows = []
    for i in range(m):
        parts = []
        for j in range(n):
            parts.append(dbc.InputGroup([
                dbc.Input(
                    id={"type": "con-coeff", "index": f"{i}_{j}"},
                    type="text", inputMode="decimal", placeholder=f"a{_sub(i+1)}{_sub(j+1)}",
                    style={"width": "72px"}, size="sm",
                ),
                dbc.InputGroupText(_xsub(j+1), className="lp-math-affix"),
                *([] if j == n - 1 else [dbc.InputGroupText("+")]),
            ], className="me-1 mb-1"))
        parts.append(dbc.Select(
            id={"type": "con-type", "index": i},
            options=[
                {"label": "≤", "value": "<="},
                {"label": "≥", "value": ">="},
                {"label": "=",  "value": "="},
            ],
            value="<=",
            style={"width": "65px"}, size="sm",
            className="me-1 mb-1 lp-math-select",
        ))
        parts.append(dbc.InputGroup([
            dbc.Input(
                id={"type": "con-rhs", "index": i},
                type="text", inputMode="decimal", placeholder=f"b{_sub(i+1)}",
                style={"width": "80px"}, size="sm",
            ),
        ], className="mb-1"))
        con_rows.append(html.Div(
            [html.Span(f"Ràng buộc {i+1}: ", className="me-2 fw-semibold align-self-center text-nowrap")] + parts,
            className="d-flex align-items-center flex-nowrap mb-2",
            style={"overflowX": "auto"},
        ))

    obj_row = html.Div(
        obj_parts,
        className="d-flex align-items-center flex-nowrap gap-1",
        style={"overflowX": "auto"},
    )
    sign_row = html.Div(
        sign_parts,
        className="d-flex align-items-center flex-nowrap gap-1",
        style={"overflowX": "auto"},
    )
    return obj_row, sign_row, con_rows


# ── Callback 2: Giải → lưu steps vào Store ────────────────────────────────

@callback(
    Output("steps-store",                       "data"),
    Output({"type": "obj-coeff", "index": ALL}, "invalid"),
    Output({"type": "con-coeff", "index": ALL}, "invalid"),
    Output({"type": "con-rhs",   "index": ALL}, "invalid"),
    Input("btn-solve", "n_clicks"),
    State("mode-select",     "value"),
    State("goal-select",     "value"),
    State("num-vars",        "value"),
    State("num-constraints", "value"),
    State({"type": "obj-coeff", "index": ALL}, "value"),
    State({"type": "con-coeff", "index": ALL}, "value"),
    State({"type": "con-type",  "index": ALL}, "value"),
    State({"type": "con-rhs",   "index": ALL}, "value"),
    State({"type": "var-sign",  "index": ALL}, "value"),
    State({"type": "obj-coeff", "index": ALL}, "id"),
    State({"type": "con-coeff", "index": ALL}, "id"),
    State({"type": "con-type",  "index": ALL}, "id"),
    State({"type": "con-rhs",   "index": ALL}, "id"),
    State({"type": "var-sign",  "index": ALL}, "id"),
    State("obj-constant", "value"),
    prevent_initial_call=True,
)
def run_solver(n_clicks, solve_mode, goal, n_vars, n_constraints,
               obj_vals, con_coeff_vals, con_types, con_rhs_vals, var_signs,
               obj_ids, con_coeff_ids, con_type_ids, con_rhs_ids, var_sign_ids,
               obj_constant_val):
    if not obj_vals:
        return (
            {"error": 'Hãy nhấn "Tạo bảng nhập" trước, sau đó điền hệ số và nhấn "Giải".', "steps": None},
            [], [], [],
        )

    n = max(1, min(UI_MAX_DIM, int(n_vars)        if n_vars        is not None else 2))
    m = max(1, min(UI_MAX_DIM, int(n_constraints) if n_constraints is not None else 2))

    def _ordered_by_index(values, ids, size):
        val_list = list(values or [])
        id_list = list(ids or [])
        index_map = {}
        for comp_id, value in zip(id_list, val_list):
            if not isinstance(comp_id, dict):
                continue
            try:
                idx = int(comp_id.get("index"))
            except (TypeError, ValueError):
                continue
            index_map[idx] = value
        return [index_map.get(i, val_list[i] if i < len(val_list) else None) for i in range(size)]

    def _ordered_grid(values, ids, rows, cols):
        val_list = list(values or [])
        id_list = list(ids or [])
        grid_map = {}
        for comp_id, value in zip(id_list, val_list):
            if not isinstance(comp_id, dict):
                continue
            idx = comp_id.get("index")
            try:
                i_str, j_str = str(idx).split("_", 1)
                i = int(i_str)
                j = int(j_str)
            except (ValueError, TypeError):
                continue
            grid_map[(i, j)] = value

        ordered = []
        for i in range(rows):
            for j in range(cols):
                flat = i * cols + j
                ordered.append(grid_map.get((i, j), val_list[flat] if flat < len(val_list) else None))
        return ordered

    ordered_obj_vals = _ordered_by_index(obj_vals, obj_ids, n)
    ordered_con_coeff_vals = _ordered_grid(con_coeff_vals, con_coeff_ids, m, n)
    ordered_con_types = _ordered_by_index(con_types, con_type_ids, m)
    ordered_con_rhs_vals = _ordered_by_index(con_rhs_vals, con_rhs_ids, m)
    ordered_var_signs = _ordered_by_index(var_signs, var_sign_ids, n)

    no_inv_obj   = [False] * len(obj_vals)
    no_inv_coeff = [False] * len(con_coeff_vals)
    no_inv_rhs   = [False] * len(con_rhs_vals)

    # ── Validate: highlight empty fields ─────────────────────────────────
    obj_inv   = [_is_missing(v) for v in ordered_obj_vals[:n]]
    coeff_inv = [_is_missing(v) for v in ordered_con_coeff_vals[:m * n]]
    rhs_inv   = [_is_missing(v) for v in ordered_con_rhs_vals[:m]]

    if any(obj_inv) or any(coeff_inv) or any(rhs_inv):
        missing = []
        missing_latex = []
        for j, inv in enumerate(obj_inv):
            if inv:
                missing.append(f"c{j+1}")
                missing_latex.append(rf"c_{{{j+1}}}")
        for i in range(m):
            for j in range(n):
                if coeff_inv[i * n + j]:
                    missing.append(f"a{i+1}{j+1}")
                    missing_latex.append(rf"a_{{{i+1}{j+1}}}")
        for i, inv in enumerate(rhs_inv):
            if inv:
                missing.append(f"b{i+1}")
                missing_latex.append(rf"b_{{{i+1}}}")
        error_msg = "Vui lòng điền đầy đủ các ô: " + ", ".join(missing)
        return (
            {
                "error": error_msg,
                "error_kind": "missing_fields",
                "missing_fields_latex": missing_latex,
                "steps": None,
                "var_names": [],
                "goal": goal,
                "objective": [],
            },
            obj_inv, coeff_inv, rhs_inv,
        )

    # ── Parse objective ───────────────────────────────────────────────────
    try:
        objective = [_parse_decimal(v, f"c{j+1}") for j, v in enumerate(ordered_obj_vals[:n])]
    except (TypeError, ValueError) as e:
        return (
            {"error": f"Hệ số hàm mục tiêu không hợp lệ: {e}", "steps": None},
            no_inv_obj, no_inv_coeff, no_inv_rhs,
        )

    # ── Parse constraints ─────────────────────────────────────────────────
    try:
        constraints = []
        rhs = []
        for i in range(m):
            row = [
                _parse_decimal(ordered_con_coeff_vals[i * n + j], f"a{i+1}{j+1}")
                for j in range(n)
            ]
            b_i = _parse_decimal(ordered_con_rhs_vals[i], f"b{i+1}")
            constraints.append(row)
            rhs.append(b_i)

        types = list(ordered_con_types[:m])
        if any(t not in {"<=", ">=", "="} for t in types):
            raise ValueError("Toán tử ràng buộc chỉ cho phép: <=, >=, =")
    except (TypeError, ValueError, IndexError) as e:
        return (
            {"error": f"Hệ số ràng buộc không hợp lệ: {e}", "steps": None},
            no_inv_obj, no_inv_coeff, no_inv_rhs,
        )

    # ── Run solver ────────────────────────────────────────────────────────
    raw_var_signs = [
        ordered_var_signs[j] if not _is_missing(ordered_var_signs[j]) else "nonnegative"
        for j in range(n)
    ]
    normalized_var_signs = [_normalize_var_sign(v) for v in raw_var_signs]
    solve_mode = str(solve_mode or "learning").strip().lower()
    if solve_mode not in {"learning", "production"}:
        solve_mode = "learning"

    payload = {
        "mode": solve_mode,
        "goal": goal,
        "objective": objective,
        "constraints": constraints,
        "types": types,
        "rhs": rhs,
        "variable_signs": normalized_var_signs,
    }

    try:
        response_data, request_error = request_solver_result(payload)
        if request_error:
            raise RuntimeError(request_error)

        if not isinstance(response_data, dict):
            raise RuntimeError("Backend trả về dữ liệu không hợp lệ.")

        response_mode = str(response_data.get("mode", solve_mode)).strip().lower()

        if response_mode == "learning":
            steps = response_data.get("steps")
            if not isinstance(steps, list) or len(steps) == 0:
                raise RuntimeError("Backend không trả về danh sách bước giải hợp lệ.")

            var_names = response_data.get("var_names")
            if not var_names:
                var_names = steps[0].get("var_names", [])
            if not var_names:
                raise RuntimeError("Thiếu var_names trong phản hồi backend.")
            production_result = None
        else:
            steps = []
            production_result = response_data.get("result")
            if not isinstance(production_result, dict):
                production_result = {}

            var_names = (
                response_data.get("var_names")
                or (response_data.get("normalized_model") or {}).get("decision_var_names")
                or [f"x{j+1}" for j in range(n)]
            )
    except Exception as e:
        return (
            {
                "error": f"Lỗi khi giải: {e}",
                "steps": None,
                "input_echo": payload,
            },
            no_inv_obj, no_inv_coeff, no_inv_rhs,
        )

    try:
        obj_constant = (
            _parse_decimal(obj_constant_val, "hằng số mục tiêu")
            if not _is_missing(obj_constant_val)
            else 0.0
        )

        serialized = {
            "steps": steps,
            "var_names": var_names,
            "goal": goal,
            "objective": objective,
            "obj_constant": obj_constant,
            "mode": response_mode,
            "backend_message": response_data.get("message"),
            "normalization": response_data.get("normalization", {}),
            "normalized_model": response_data.get("normalized_model", {}),
            "production_result": production_result,
            "input_echo": payload,
            "error": None,
        }
    except Exception as e:
        return (
            {"error": f"Lỗi khi serialize: {e}", "steps": None},
            no_inv_obj, no_inv_coeff, no_inv_rhs,
        )

    return serialized, no_inv_obj, no_inv_coeff, no_inv_rhs


# ── Callback 3: Khi steps hoặc mode thay đổi → render result-area ─────────

@callback(
    Output("result-area", "children"),
    Input("steps-store",  "data"),
    Input("display-mode", "data"),
    Input("algebra-panel-visible", "data"),
    Input("show-normalized-model", "value"),
)
def render_result(store_data, display_mode, algebra_visible, show_normalized_model=True):
    if algebra_visible is None:
        algebra_visible = True
    if store_data is None:
        return html.P(
            'Hãy nhấn "Giải" để xem kết quả.',
            className="text-muted fst-italic",
        )

    if store_data.get("error"):
        missing_latex = store_data.get("missing_fields_latex") or []
        if missing_latex:
            labels = []
            for idx, expr in enumerate(missing_latex):
                labels.append(dk.DashKatex(expression=expr, displayMode=False))
                if idx < len(missing_latex) - 1:
                    labels.append(html.Span(",", className="mx-1 text-muted"))

            error_alert = dbc.Alert(
                [
                    html.Div("Vui lòng điền đầy đủ các ô:", className="fw-semibold mb-2"),
                    html.Div(labels, className="d-flex flex-wrap align-items-center"),
                ],
                color="danger",
            )
        else:
            error_alert = dbc.Alert(store_data["error"], color="danger")
        input_echo = store_data.get("input_echo")
        if isinstance(input_echo, dict):
            echo_card = dbc.Alert(
                [
                    html.Div("Input echo để tái lập lỗi:", className="fw-semibold mb-2"),
                    html.Pre(
                        json.dumps(input_echo, ensure_ascii=False, indent=2),
                        className="mb-0",
                        style={"whiteSpace": "pre-wrap"},
                    ),
                ],
                color="warning",
                className="mt-2",
            )
            return html.Div([error_alert, echo_card])
        return error_alert

    mode = str(store_data.get("mode") or "learning").lower()
    var_names    = store_data.get("var_names") or []
    goal         = store_data.get("goal") or "max"
    objective    = store_data.get("objective") or []
    obj_constant = float(store_data.get("obj_constant") or 0)
    normalization = store_data.get("normalization") or {}
    normalized_model = store_data.get("normalized_model") or {}
    input_echo = store_data.get("input_echo") or {}

    normalization_notice = None
    rhs_flips = normalization.get("rhs_flips") or []
    substitutions = normalization.get("unrestricted_substitutions") or []

    messages = []
    if rhs_flips:
        messages.append(
            dk.DashKatex(
                expression=rf"\text{{Chuẩn hóa RHS: có }} {len(rhs_flips)}\ \text{{ràng buộc với }} b_i < 0\ \text{{được nhân }}(-1)",
                displayMode=False,
            )
        )
    if substitutions:
        for sub in substitutions:
            if sub.get("original") and sub.get("plus") and sub.get("minus"):
                messages.append(html.Span("Tách biến tự do: "))
                messages.append(
                    dk.DashKatex(
                        expression=rf"{_var_label(sub['original'])} = {_var_label(sub['plus'])} - {_var_label(sub['minus'])}",
                        displayMode=False,
                    )
                )
            elif sub.get("formula"):
                messages.append(html.Span(f"Tách biến tự do: {sub['formula']}"))

    if messages:
        normalization_notice = dbc.Alert(
            html.Div(
                [
                    html.Div("Chi tiết chuẩn hóa Stage 1:", className="fw-semibold mb-2"),
                    *[html.Div(msg, className="mb-1") for msg in messages],
                ]
            ),
            color="info",
            className="mb-3",
        )

    model_notice = None
    if bool(show_normalized_model) and _should_show_normalized_model_notice(normalized_model, normalization, input_echo):
        model_notice = _render_normalized_model_notice(normalized_model)

    constant_notice = None
    if abs(obj_constant) > 1e-12:
        sign = "+" if obj_constant > 0 else "-"
        constant_notice = dbc.Alert(
            html.Div(
                [
                    _hover_term(
                        "hiệu chỉnh hằng số mục tiêu",
                        "d là hằng số cộng thêm vào giá trị mục tiêu cuối: Z = Z_tuyen_tinh + d.",
                        "objective-offset",
                    ),
                    dk.DashKatex(
                        expression=rf"d = {sign}{abs(obj_constant):g},\quad Z = Z_{{\text{{tuyen tinh}}}} + d",
                        displayMode=False,
                    ),
                ],
                className="d-flex align-items-center flex-wrap gap-2",
            ),
            color="warning",
            className="mb-3",
        )

    if mode == "production":
        result = store_data.get("production_result") or {}
        status = str(result.get("status") or "unknown")
        term_reason = result.get("termination_reason") or "n/a"
        iterations = result.get("iterations")
        objective_value = result.get("objective_value")
        solution_map = result.get("solution_map") or {}
        sensitivity = result.get("sensitivity") or {}

        color = "secondary"
        if status == "optimal":
            color = "success"
        elif status in {"unbounded", "infeasible", "numerical_error"}:
            color = "danger"
        elif status in {"iteration_limit", "fallback", "not_implemented"}:
            color = "warning"

        status_vi = {
            "optimal": "Tối ưu",
            "unbounded": "Không bị chặn",
            "infeasible": "Vô nghiệm",
            "numerical_error": "Lỗi số học",
            "iteration_limit": "Chạm giới hạn lặp",
            "fallback": "Dùng bộ giải dự phòng",
            "not_implemented": "Chưa hỗ trợ",
            "unknown": "Không xác định",
        }.get(status, status)

        reason_vi = {
            "optimality_reached": "Đã thỏa điều kiện tối ưu",
            "phase2_iteration_limit": "Pha 2 chạm giới hạn vòng lặp",
            "phase1_iteration_limit": "Pha 1 chạm giới hạn vòng lặp",
            "phase1_positive_w": "Kết thúc Pha 1 với W > 0",
            "phase1_no_valid_pivot": "Pha 1 không có pivot hợp lệ",
            "phase2_basis_recovery_failed": "Không khôi phục được cơ sở cho Pha 2",
            "singular_basis": "Ma trận cơ sở suy biến",
            "dual_solve_failed": "Giải hệ song đối thất bại",
            "direction_solve_failed": "Giải hướng pivot thất bại",
            "ratio_test_failed": "Kiểm tra tỷ số thất bại",
            "empty_steps": "Không nhận được bước giải",
            "n/a": "không có",
        }.get(str(term_reason), str(term_reason))

        summary_blocks = [
            html.Div(f"Trạng thái: {status_vi}", className="fw-semibold"),
            html.Div(f"Lý do dừng: {reason_vi}", className="small text-muted"),
        ]
        if iterations is not None:
            summary_blocks.append(html.Div(f"Số vòng lặp: {iterations}", className="small text-muted"))
        if objective_value is not None:
            summary_blocks.append(dk.DashKatex(expression=rf"Z^* = {_fmt(objective_value)}", displayMode=False))
        if solution_map:
            summary_blocks.append(
                html.Pre(
                    json.dumps(solution_map, ensure_ascii=False, indent=2),
                    className="mb-0 mt-2",
                    style={"whiteSpace": "pre-wrap"},
                )
            )
        if sensitivity:
            summary_blocks.append(html.Hr(className="my-2"))
            summary_blocks.append(html.Div("Báo cáo độ nhạy", className="fw-semibold"))
            reduced_costs = sensitivity.get("reduced_costs") or {}
            dual_prices = sensitivity.get("dual_prices") or {}
            binding_constraints = sensitivity.get("binding_constraints") or []

            if reduced_costs:
                summary_blocks.append(html.Div("Hệ số giảm:", className="small mt-1"))
                summary_blocks.append(
                    html.Pre(
                        json.dumps(reduced_costs, ensure_ascii=False, indent=2),
                        className="mb-0",
                        style={"whiteSpace": "pre-wrap"},
                    )
                )
            if dual_prices:
                summary_blocks.append(html.Div("Giá song đối:", className="small mt-1"))
                summary_blocks.append(
                    html.Pre(
                        json.dumps(dual_prices, ensure_ascii=False, indent=2),
                        className="mb-0",
                        style={"whiteSpace": "pre-wrap"},
                    )
                )
            if binding_constraints:
                summary_blocks.append(
                    html.Div(
                        f"Ràng buộc chặt: {binding_constraints}",
                        className="small mt-1",
                    )
                )

        production_panel = dbc.Alert(summary_blocks, color=color, className="mb-0")
        notices = [n for n in (model_notice, normalization_notice, constant_notice) if n is not None]
        return html.Div(notices + [production_panel])

    steps = _deserialize_steps(store_data.get("steps") or [])

    if display_mode == "algebra":
        algebra_content = render_algebra_mode(steps, var_names, goal, objective, obj_constant)
        notices = [n for n in (model_notice, normalization_notice, constant_notice) if n is not None]
        if notices:
            merged_children = list(notices)
            if isinstance(algebra_content, list):
                merged_children.extend(algebra_content)
            else:
                merged_children.append(algebra_content)
            return html.Div(merged_children)
        return algebra_content

    # "table" mode: algebra explanation (left) + simplex tableau (right)
    algebra_panel = render_algebra_mode_classic(steps, var_names, goal, objective, obj_constant)
    tableau_panel = render_table_mode(steps, var_names, obj_constant, goal)

    algebra_title = html.H6(
        "Giải thích Đại số",
        className="text-center fw-bold mb-3 text-primary border-bottom pb-2",
    )
    tableau_header = html.H6(
        "Bảng Simplex",
        className="text-center fw-bold mb-3 text-primary border-bottom pb-2",
    )

    if algebra_visible:
        table_layout = dbc.Row(
            [
                dbc.Col(
                    [
                        algebra_title,
                        html.Div(
                            algebra_panel,
                            style={"overflowY": "auto", "maxHeight": "72vh", "paddingRight": "6px"},
                        ),
                    ],
                    md=6,
                    className="pe-3 border-end",
                ),
                dbc.Col(
                    [
                        tableau_header,
                        html.Div(
                            tableau_panel,
                            style={"overflowY": "auto", "maxHeight": "72vh", "overflowX": "auto"},
                        ),
                    ],
                    md=6,
                    className="ps-3",
                ),
            ],
            className="g-0",
        )
        notices = [n for n in (model_notice, normalization_notice, constant_notice) if n is not None]
        if notices:
            return html.Div(notices + [table_layout])
        return table_layout
    else:
        compact_layout = html.Div(
            [
                tableau_header,
                html.Div(
                    tableau_panel,
                    style={"overflowY": "auto", "maxHeight": "72vh", "overflowX": "auto"},
                ),
            ]
        )
        notices = [n for n in (model_notice, normalization_notice, constant_notice) if n is not None]
        if notices:
            return html.Div(notices + [compact_layout])
        return compact_layout


# ── Callback 4: Toggle mode button ────────────────────────────────────────

@callback(
    Output("display-mode",    "data"),
    Output("btn-toggle-mode", "children"),
    Input("btn-toggle-mode",  "n_clicks"),
    State("display-mode",     "data"),
    prevent_initial_call=True,
)
def _toggle_mode(n_clicks, current_mode):
    if current_mode == "algebra":
        return "table", html.Img(src="/assets/Math.svg",  style={"width": "28px", "height": "28px"})
    return "algebra", html.Img(src="/assets/Table.svg", style={"width": "28px", "height": "28px"})


# ── Callback 5: Toggle algebra panel visibility ────────────────────────────

@callback(
    Output("algebra-panel-visible", "data"),
    Input("btn-toggle-algebra", "n_clicks"),
    State("algebra-panel-visible", "data"),
    prevent_initial_call=True,
)
def _toggle_algebra_panel(n_clicks, current):
    if current is None:
        current = True
    return not current


# ── Callback 6: Update eye button icon & visibility ───────────────────────

@callback(
    Output("btn-toggle-algebra",     "style"),
    Output("btn-toggle-algebra-img", "src"),
    Input("display-mode",            "data"),
    Input("algebra-panel-visible",   "data"),
)
def _update_eye_button(display_mode, algebra_visible):
    if algebra_visible is None:
        algebra_visible = True
    show = display_mode == "table"
    style = {"lineHeight": "1", "display": "inline-flex" if show else "none"}
    src = "/assets/visibility.svg" if algebra_visible else "/assets/visibility off.svg"
    return style, src


# ── Clientside callback 5: Hover-link Ratio ↔ b / pivot-col cells ─────────

clientside_callback(
    """
    function(children) {
        var area = document.getElementById('result-area');
        if (!area) return '';
        if (window._simplexHoverIn) {
            area.removeEventListener('mouseover', window._simplexHoverIn);
            area.removeEventListener('mouseout',  window._simplexHoverOut);
        }
        window._simplexHoverIn = function(e) {
            var cell = e.target.closest && e.target.closest('.ratio-cell');
            if (!cell) return;
            var tbl = cell.closest('table');
            if (!tbl) return;
            var row = cell.getAttribute('data-row');
            tbl.querySelectorAll(
                '[data-row="' + row + '"].b-cell, [data-row="' + row + '"].pcol-cell'
            ).forEach(function(el) { el.classList.add('highlight-linked'); });
        };
        window._simplexHoverOut = function(e) {
            var cell = e.target.closest && e.target.closest('.ratio-cell');
            if (!cell) return;
            var tbl = cell.closest('table');
            if (!tbl) return;
            var row = cell.getAttribute('data-row');
            tbl.querySelectorAll(
                '[data-row="' + row + '"].b-cell, [data-row="' + row + '"].pcol-cell'
            ).forEach(function(el) { el.classList.remove('highlight-linked'); });
        };
        area.addEventListener('mouseover', window._simplexHoverIn);
        area.addEventListener('mouseout',  window._simplexHoverOut);
        return '';
    }
    """,
    Output("_hover-dummy", "data"),
    Input("result-area", "children"),
)

