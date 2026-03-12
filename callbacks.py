"""
callbacks.py
------------
Dash callbacks — all interactivity logic.
"""

import numpy as np

from dash import Input, Output, State, ALL, callback, clientside_callback, html
import dash_bootstrap_components as dbc
import dash_katex as dk

from simplex_engine import solve_steps, standardize
from latex_helper import (
    format_objective,
    format_standard_form,
    format_pivot_choice,
    format_updated_equations,
    format_w_objective,
    _var_label,
)


# ── UI micro-helpers ────────────────────────────────────────────────────

_SUB_TRANS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
def _sub(n: int) -> str:
    """Convert integer to Unicode subscript string, e.g. 12 → '₁₂'."""
    return str(n).translate(_SUB_TRANS)

def _xsub(j: int):
    """Return an html.Span rendering xⱼ (italic x with subscript)."""
    return html.Span(["x", html.Sub(str(j))], style={"fontStyle": "italic"})

def _step_header(step_num: int, title: str, tooltip_text: str, uid: str):
    """Numbered step title with hover tooltip."""
    tid = f"tt-{uid}"
    return html.Div([
        html.Span(
            f"Bước {step_num}: {title}",
            id=tid,
            className="fw-semibold text-primary d-inline-block",
            style={"cursor": "help", "borderBottom": "1px dashed #0d6efd"},
        ),
        dbc.Tooltip(tooltip_text, target=tid, placement="top"),
    ], className="mt-3 mb-1")


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
            "(W = \u03a3a\u1d62 \u2192 0) \u0111\u1ec3 t\u00ecm BFS cho Pha 2."
        ),
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
            "\u274c Pha 1 k\u1ebft th\u00fac: bi\u1ebfn nh\u00e2n t\u1ea1o \u2260 0 "
            "\u2192 B\u00e0i to\u00e1n v\u00f4 nghi\u1ec7m.",
            color="danger", className="mb-3",
        ))
        return blocks, False

    blocks.append(dbc.Alert(
        "\u2705 Pha 1 ho\u00e0n th\u00e0nh: t\u1ea5t c\u1ea3 bi\u1ebfn nh\u00e2n t\u1ea1o = 0 \u2192 BFS kh\u1ea3 thi. "
        "Lo\u1ea1i b\u1ecf c\u1ed9t bi\u1ebfn nh\u00e2n t\u1ea1o, chuy\u1ec3n sang Pha 2.",
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

def render_tableau_static(step, var_names, z_offset=0.0, obj_label="Z"):
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
                dk.DashKatex(
                    expression=r"\theta_i = \frac{b_i}{a_{ij}},\ a_{ij} > 0"
                ),
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
    z_cells.append(html.Td(_cell_katex(tableau[0, -1] + z_offset)))
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
            return (
                "Thêm biến bù (slack sᵢ ≥ 0) để đổi ràng buộc ≤ thành đẳng thức. "
                "Cơ sở ban đầu là toàn bộ biến bù, BFS: mọi xⱼ = 0."
            )
        if name == "Nghiệm tối ưu":
            return (
                "Mọi hệ số hàng Z đều ≥ 0 (max) hoặc ≤ 0 (min) → điều kiện tối ưu thỏa. "
                "Đọc nghiệm từ cột b của hàng cơ sở."
            )
        if name == "Không bị chặn":
            return (
                "Cột biến vào toàn số ≤ 0 → không có hàng pivot hợp lệ. "
                "Hàm mục tiêu không bị chặn (unbounded)."
            )
        if name == "Vô nghiệm":
            return (
                "biến thêm vào (a_i) vẫn còn trong cơ sở với giá trị ≠ 0 khi đạt điều kiện dừng. "
                "Hệ ràng buộc mâu thuẫn → bài toán vô nghiệm."
            )
        # Iteration step — include entering/leaving info
        pc = step.get("pivot_col")
        pr = step.get("pivot_row")
        entering = var_names[pc] if pc is not None else "?"
        leaving  = step["basis"][pr - 1] if pr is not None else "?"
        return (
            f"Biến vào: {entering} (hệ số C̄ âm nhất / dương nhất). "
            f"Biến ra: {leaving} (min-ratio test). "
            "Thực hiện phép xoay để cập nhật tableau."
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
                "❌ Bài toán không bị chặn (Unbounded) — hàm mục tiêu tiến đến ∞.",
                color="danger", className="mt-3 mb-0",
            )
        if name == "Vô nghiệm":
            return dbc.Alert(
                "❌ Bài toán vô nghiệm (Infeasible) — hệ ràng buộc mâu thuẫn nhau.",
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
                                      z_offset=0.0, obj_label="W"),
            ]
        else:
            block_children = [
                _step_header(step, idx),
                render_tableau_static(step, var_names,
                                      z_offset=obj_constant),
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
        art_vars  = p1_steps[0].get("art_vars", [])

        blocks.append(dbc.Badge(
            "Pha 1 — Tìm lời giải cơ sở khả thi (BFS)",
            color="warning", pill=True,
            className="fs-6 mb-3 px-3 py-2",
            style={"color": "#664d03"},
        ))
        blocks.append(dbc.Alert(
            html.Div([
                html.Span("Thêm biến thêm vào: "),
                dk.DashKatex(expression=", ".join(_var_label(v) for v in art_vars)),
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
                "❌ Pha 1 kết thúc: biến thêm vào ≠ 0 → Bài toán vô nghiệm.",
                color="danger", className="mb-3",
            ))
            return blocks

        blocks.append(dbc.Alert(
            html.Div([
                html.Strong("\u2705 Pha 1 ho\u00e0n th\u00e0nh: "),
                html.Span("W = 0. Lo\u1ea1i b\u1ecf c\u1ed9t "),
                dk.DashKatex(expression=", ".join(_var_label(v) for v in art_vars)),
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
                "Thêm biến bù (slack s_i ≥ 0) để chuyển ràng buộc "
                "≤ thành dạng đẳng thức. Hệ phương trình có m ẩn."
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
            4, "Kiểm tra điều kiện tối ưu (hệ số C̄_j)",
            tooltip_text=(
                "Max: tối ưu khi mọi C̄_j ≥ 0. "
                "Min: tối ưu khi mọi C̄_j ≤ 0. "
                "Nếu còn C̄_j vi phạm, biến cơ sở phù hợp sẽ được đưa vào."
            ),
            uid=f"{uid}s4",
        ))
        obj_row = t_before[0, :-1]
        cj_parts = [
            rf"\bar{{c}}_{{{_var_label(var_names[j])}}} = {_fmt(obj_row[j])}"
            for j in range(len(var_names))
        ]
        not_opt = (any(c < 0 for c in obj_row) if goal == "max"
                   else any(c > 0 for c in obj_row))
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
            5, "Chọn biến vào & biến ra (Min Ratio Test)",
            tooltip_text=(
                "Biến vào: cột có C̄_j âm nhất (max) / dương nhất (min). "
                "Biến ra: min ratio test — θ_i = b_i / a_ij với a_ij > 0; "
                "chọn hàng có θ nhỏ nhất."
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
                "Chia hàng pivot cho phần tử chốt (phần tử → 1). "
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
            pc_ub  = after.get("pivot_col")
            ub_var = _var_label(var_names[pc_ub]) if pc_ub is not None else "?"
            iter_block.append(dbc.Alert(
                [
                    html.Strong("Bước 7: ❌ KHÔNG BỊ CHẶN (Unbounded) "),
                    html.Span("— cột "),
                    dk.DashKatex(expression=ub_var, displayMode=False),
                    html.Span(" không có hàng pivot hợp lệ "
                              "(tất cả phần tử ≤ 0). "
                              "Hàm mục tiêu tiến đến ∞."),
                ],
                color="danger", className="mt-3 mb-0",
            ))
        elif after["step_name"] == "Vô nghiệm":
            iter_block.append(dbc.Alert(
                html.Strong("❌ VÔ NGHIỆM (Infeasible): Hệ ràng buộc mâu thuẫn, biến thêm vào vẫn ở trong cơ sở."),
                color="danger", className="mt-3 mb-0",
            ))
        else:
            iter_block.append(html.P(
                "Bước 7: Tableau chưa tối ưu → tiếp tục lần lặp tiếp theo.",
                className="text-muted fst-italic mt-2 mb-0",
            ))

        blocks.append(html.Div(iter_block))

    # Edge cases: no pivots in Phase 2
    if not iter_steps and p2_steps:
        last_name = p2_steps[-1]["step_name"]
        if last_name in ("Không bị chặn"):
            pc_ub  = p2_steps[-1].get("pivot_col")
            ub_var = _var_label(var_names[pc_ub]) if pc_ub is not None else "?"
            blocks.append(dbc.Alert(
                f"❌ Bài toán không bị chặn — cột {ub_var} không có hàng pivot hợp lệ.",
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
        return lhs + " = " + " ".join(terms)

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
        art_vars  = p1_steps[0].get("art_vars", [])
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
                "Ràng buộc dạng '=' hoặc '≥' không có biến bù tự nhiên → thêm biến thêm vào. "
                "Pha 1 tối thiểu hóa hàm mục tiêu nhân tạo: ",
                className="me-2",
            ),
            dk.DashKatex(expression=f"W = {format_w_objective(art_vars)}", displayMode=False),
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
                    html.Span(" → W chưa tối thiểu, cần tiếp tục.", className="ms-2"),
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
                html.Span(
                    f" là biến vào (hệ số C̄ᵂ = {_fmt(c_enter_w)} — âm nhất).",
                    className="ms-1",
                ),
            ], className="d-flex align-items-center flex-wrap mb-2"))

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
                        "(hệ số = 0 → bỏ qua)",
                        className="text-muted ms-2 small fst-italic",
                    )
                elif a_p1 < 0:
                    note_p1 = html.Span(
                        "(hệ số < 0 → không ràng buộc)",
                        className="text-muted ms-2 small fst-italic",
                    )
                else:
                    ratio_p1    = b_v_p1 / a_p1
                    is_pivot_p1 = (i_p1 + 1 == pivot_row_p1)
                    note_p1 = html.Span([
                        html.Span(f"θ = {_fmt(b_v_p1)} / {_fmt(a_p1)} = {_fmt(ratio_p1)}"),
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
                html.Span("→ ", className="ms-2"),
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
                "❌ Pha 1 kết thúc: biến thêm vào ≠ 0 → Bài toán vô nghiệm.",
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
                html.Span("→ Tất cả ", className="ms-2"),
                dk.DashKatex(expression=r"\bar{C}^W_j \geq 0"),
                html.Span(f" và W = {_fmt(w_final)} = 0 → ", className="ms-1"),
                html.Span("BFS khả thi đã tìm được.",
                          className="fw-bold text-success"),
            ], className="d-flex align-items-center flex-wrap gap-1 mb-2"))

        blocks.append(dbc.Alert(
            html.Div([
                html.Strong("Pha 1 hoàn thành. "),
                html.Span("Loại bỏ các biến thêm vào ("),
                dk.DashKatex(expression=", ".join(_var_label(v) for v in art_vars)),
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
            blocks.append(html.Div(
                "→ Tất cả C̄_j thỏa mãn điều kiện tối ưu → Lời giải ban đầu đã là tối ưu.",
                className="text-success fw-semibold ms-2 mt-1",
            ))
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
            pc_ub  = terminal.get("pivot_col")
            ub_var = _var_label(var_names[pc_ub]) if pc_ub is not None else "?"
            blocks.append(dbc.Alert(
                f"❌ Bài toán không bị chặn — cột {ub_var} không có hàng pivot hợp lệ.",
                color="danger",
            ))
        elif terminal["step_name"] == "Vô nghiệm":
            blocks.append(dbc.Alert(
                "❌ Bài toán vô nghiệm (Infeasible) — hệ ràng buộc mâu thuẫn nhau.",
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
                html.Span(" → nên bài toán chưa tối ưu, cần thực hiện thêm bước xoay.",
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
            html.Span("+ ", className="ms-2"),
            dk.DashKatex(expression=entering_label),
            html.Span(
                f" là biến cơ sở mới (có hệ số C̄ = {_fmt(c_enter)}"
                f" — {sign_word} trong các biến không cơ sở).",
                className="ms-1",
            ),
        ], className="d-flex align-items-center flex-wrap mb-2"))

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
                note = html.Span("(hệ số = 0 → bỏ qua)", className="text-muted ms-2 small fst-italic")
            elif a < 0:
                note = html.Span(
                    f"(tăng {entering} → {bv} tăng → không ràng buộc)",
                    className="text-muted ms-2 small fst-italic",
                )
            else:
                ratio    = b_val / a
                is_pivot = (i + 1 == pivot_row)
                note = html.Span([
                    html.Span(f"θ = {_fmt(b_val)} / {_fmt(a)} = {_fmt(ratio)}"),
                    html.Span(" ← chọn", className="text-success fw-bold ms-1") if is_pivot else html.Span(""),
                ], className="text-success fw-semibold ms-2 small" if is_pivot else "text-muted ms-2 small")

            blocks.append(html.Div([
                html.Span(f"Từ {eq_lbl}:", className="text-muted small"),
                dk.DashKatex(expression=eq_str),
                note,
            ], className="ms-4 mb-1 d-flex align-items-center flex-wrap gap-2"))

        blocks.append(html.Div([
            html.Span("→ Ta chọn ", className="ms-2"),
            dk.DashKatex(expression=leaving_label),
            html.Span(" là biến không cơ sở mới. → Viết lại hệ phương trình chính tắc.", className="ms-1"),
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

            # Build Cj ≥/≤ 0 summary line
            signs_parts = []
            for j, v in enumerate(var_names):
                if v not in nb_after:
                    continue
                c  = t_after[0, j] if goal == "min" else -t_after[0, j]
                cl = _var_label(v)
                cmp = r"\geq 0" if goal == "min" else r"\leq 0"
                signs_parts.append(rf"\bar{{C}}_{{{cl}}} = {_fmt(c)} {cmp}")

            suffix = "≥ 0" if goal == "min" else "≤ 0"
            blocks.append(html.Div(
                f"→ Tất cả C̄_j {suffix} → Lời giải hiện tại là tối ưu.",
                className="text-success fw-semibold ms-2 mt-1",
            ))

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
            pc_ub  = after.get("pivot_col")
            ub_var = _var_label(var_names[pc_ub]) if pc_ub is not None else "?"
            blocks.append(dbc.Alert(
                [
                    html.Strong("❌ Không bị chặn (Unbounded): "),
                    html.Span(
                        f"Cột {ub_var} không có hàng pivot hợp lệ "
                        "(tất cả hệ số ≤ 0). Hàm mục tiêu tiến đến ∞."
                    ),
                ],
                color="danger", className="mt-3",
            ))
        elif after["step_name"] == "Vô nghiệm":
            blocks.append(dbc.Alert(
                html.Strong("❌ VÔ NGHIỆM (Infeasible): Hệ ràng buộc mâu thuẫn, biến thêm vào vẫn ở trong cơ sở."),
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
    Output("constraint-inputs", "children"),
    Input("num-vars",        "value"),
    Input("num-constraints", "value"),
)
def generate_inputs(n_vars, n_constraints):
    n = max(1, min(10, int(n_vars)        if n_vars        is not None else 2))
    m = max(1, min(10, int(n_constraints) if n_constraints is not None else 2))

    # ── Objective coefficient inputs ──────────────────────────────────────
    obj_parts = []
    for j in range(n):
        obj_parts.append(dbc.InputGroup([
            dbc.Input(
                id={"type": "obj-coeff", "index": j},
                type="number", placeholder=f"c{_sub(j+1)}",
                style={"width": "72px"}, size="sm",
            ),
            dbc.InputGroupText(_xsub(j+1)),
            *([] if j == n - 1 else [dbc.InputGroupText("+")]),
        ], className="me-1 mb-1"))

    # ── Constraint rows ───────────────────────────────────────────────────
    # Coefficient indices: flat row-major → con_coeff_vals[i*n + j] in solve cb
    con_rows = []
    for i in range(m):
        parts = []
        for j in range(n):
            parts.append(dbc.InputGroup([
                dbc.Input(
                    id={"type": "con-coeff", "index": i * 10 + j},
                    type="number", placeholder=f"a{_sub(i+1)}{_sub(j+1)}",
                    style={"width": "72px"}, size="sm",
                ),
                dbc.InputGroupText(_xsub(j+1)),
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
            className="me-1 mb-1",
        ))
        parts.append(dbc.InputGroup([
            dbc.Input(
                id={"type": "con-rhs", "index": i},
                type="number", placeholder=f"b{_sub(i+1)}",
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
    return obj_row, con_rows


# ── Callback 2: Giải → lưu steps vào Store ────────────────────────────────

@callback(
    Output("steps-store",                       "data"),
    Output({"type": "obj-coeff", "index": ALL}, "invalid"),
    Output({"type": "con-coeff", "index": ALL}, "invalid"),
    Output({"type": "con-rhs",   "index": ALL}, "invalid"),
    Input("btn-solve", "n_clicks"),
    State("goal-select",     "value"),
    State("num-vars",        "value"),
    State("num-constraints", "value"),
    State({"type": "obj-coeff", "index": ALL}, "value"),
    State({"type": "con-coeff", "index": ALL}, "value"),
    State({"type": "con-type",  "index": ALL}, "value"),
    State({"type": "con-rhs",   "index": ALL}, "value"),
    State("obj-constant", "value"),
    prevent_initial_call=True,
)
def run_solver(n_clicks, goal, n_vars, n_constraints,
               obj_vals, con_coeff_vals, con_types, con_rhs_vals,
               obj_constant_val):
    if not obj_vals:
        return (
            {"error": 'Hãy nhấn "Tạo bảng nhập" trước, sau đó điền hệ số và nhấn "Giải".', "steps": None},
            [], [], [],
        )

    n = max(1, min(10, int(n_vars)        if n_vars        is not None else 2))
    m = max(1, min(10, int(n_constraints) if n_constraints is not None else 2))

    no_inv_obj   = [False] * len(obj_vals)
    no_inv_coeff = [False] * len(con_coeff_vals)
    no_inv_rhs   = [False] * len(con_rhs_vals)

    # ── Validate: highlight empty fields ─────────────────────────────────
    obj_inv   = [v is None for v in obj_vals[:n]]
    coeff_inv = [v is None for v in con_coeff_vals[:m * n]]
    rhs_inv   = [v is None for v in con_rhs_vals[:m]]

    if any(obj_inv) or any(coeff_inv) or any(rhs_inv):
        missing = []
        for j, inv in enumerate(obj_inv):
            if inv:
                missing.append(f"c{j+1}")
        for i in range(m):
            for j in range(n):
                if coeff_inv[i * n + j]:
                    missing.append(f"a{i+1}{j+1}")
        for i, inv in enumerate(rhs_inv):
            if inv:
                missing.append(f"b{i+1}")
        error_msg = "Vui lòng điền đầy đủ các ô: " + ", ".join(missing)
        return (
            {"error": error_msg, "steps": None, "var_names": [], "goal": goal, "objective": []},
            obj_inv, coeff_inv, rhs_inv,
        )

    # ── Parse objective ───────────────────────────────────────────────────
    try:
        objective = [float(v) for v in obj_vals[:n]]
    except (TypeError, ValueError) as e:
        return (
            {"error": f"Hệ số hàm mục tiêu không hợp lệ: {e}", "steps": None},
            no_inv_obj, no_inv_coeff, no_inv_rhs,
        )

    # ── Parse constraints ─────────────────────────────────────────────────
    try:
        constraints = []
        for i in range(m):
            row = [float(con_coeff_vals[i * n + j]) for j in range(n)]
            rhs = float(con_rhs_vals[i])
            row.append(rhs)
            constraints.append(row)
        types = list(con_types[:m])
    except (TypeError, ValueError, IndexError) as e:
        return (
            {"error": f"Hệ số ràng buộc không hợp lệ: {e}", "steps": None},
            no_inv_obj, no_inv_coeff, no_inv_rhs,
        )

    # ── Run solver ────────────────────────────────────────────────────────
    try:
        init      = standardize(objective, constraints, types, goal)
        var_names = init["var_names"]
        steps     = solve_steps(objective, constraints, types, goal)
    except Exception as e:
        return (
            {"error": f"Lỗi khi giải: {e}", "steps": None},
            no_inv_obj, no_inv_coeff, no_inv_rhs,
        )

    obj_constant = float(obj_constant_val) if obj_constant_val is not None else 0.0
    return _serialize_steps(steps, var_names, goal, objective, obj_constant), no_inv_obj, no_inv_coeff, no_inv_rhs


# ── Callback 3: Khi steps hoặc mode thay đổi → render result-area ─────────

@callback(
    Output("result-area", "children"),
    Input("steps-store",  "data"),
    Input("display-mode", "data"),
    Input("algebra-panel-visible", "data"),
)
def render_result(store_data, display_mode, algebra_visible):
    if algebra_visible is None:
        algebra_visible = True
    if store_data is None:
        return html.P(
            'Hãy nhấn "Giải" để xem kết quả.',
            className="text-muted fst-italic",
        )

    if store_data.get("error"):
        return dbc.Alert(store_data["error"], color="danger")

    steps        = _deserialize_steps(store_data["steps"])
    var_names    = store_data["var_names"]
    goal         = store_data["goal"]
    objective    = store_data["objective"]
    obj_constant = float(store_data.get("obj_constant") or 0)

    if display_mode == "algebra":
        return render_algebra_mode(steps, var_names, goal, objective, obj_constant)

    # "table" mode: algebra explanation (left) + simplex tableau (right)
    algebra_panel = render_algebra_mode_classic(steps, var_names, goal, objective, obj_constant)
    tableau_panel = render_table_mode(steps, var_names, obj_constant, goal)

    algebra_title = html.H6(
        "Giải thích Đại số",
        className="text-center fw-bold mb-3 text-primary border-bottom pb-2",
    )
    tableau_header = html.H6(
        "Simplex Tableau",
        className="text-center fw-bold mb-3 text-primary border-bottom pb-2",
    )

    if algebra_visible:
        return dbc.Row(
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
    else:
        return html.Div(
            [
                tableau_header,
                html.Div(
                    tableau_panel,
                    style={"overflowY": "auto", "maxHeight": "72vh", "overflowX": "auto"},
                ),
            ]
        )


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

