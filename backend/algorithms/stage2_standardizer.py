import numpy as np

try:
    from ..utils.numeric_policy import EPS_OPT
except ImportError:
    from utils.numeric_policy import EPS_OPT

def _find_natural_basis(partial, m, n_cols, var_names):
    """
    Scan the (m × n_cols) constraint matrix *right-to-left* for unit-vector
    columns that can serve as a natural initial basis.
    """
    basis_name = {}
    used_cols  = set()
    for col in range(n_cols - 1, -1, -1):
        col_vec      = partial[:, col]
        nonzero_rows = [r for r in range(m) if abs(col_vec[r]) > EPS_OPT]
        if len(nonzero_rows) == 1:
            r = nonzero_rows[0]
            if (abs(col_vec[r] - 1.0) < EPS_OPT
                    and r not in basis_name
                    and col not in used_cols):
                basis_name[r] = var_names[col]
                used_cols.add(col)
    return basis_name, used_cols


def build_standard_form(objective, constraints, types, goal, decision_var_names=None):
    """
    STAGE 2: Khởi tạo Dạng Chuẩn Phức Hợp.
    - Kế thừa chuẩn hóa Slack / Surplus / Artificial cũ.
    - Setup logic dò cơ sở tự nhiên (Natural Basis Detection).
    - Tạo dòng W cho Pha 1, và dòng Z cho Pha 2.
    """
    goal_norm = (goal or "max").lower()
    n_vars = len(objective)
    m      = len(constraints)

    if decision_var_names and len(decision_var_names) == n_vars:
        base_var_names = [str(v) for v in decision_var_names]
    else:
        base_var_names = [f"x{j+1}" for j in range(n_vars)]

    # ── Slack / surplus ───────────────────────────────────────────────────
    slack_info = []
    s_count    = 1
    for i, t in enumerate(types):
        if t == "<=":
            slack_info.append((i, 1.0, f"s{s_count}"))
            s_count += 1
        elif t == ">=":
            slack_info.append((i, -1.0, f"s{s_count}"))
            s_count += 1

    n_slack     = len(slack_info)
    n_pre_art   = n_vars + n_slack
    pre_var_names = (base_var_names + [sv[2] for sv in slack_info])

    # Partial constraint matrix (before artificials)
    partial = np.zeros((m, n_pre_art), dtype=float)
    for i, row in enumerate(constraints):
        for j in range(n_vars):
            partial[i, j] = float(row[j])
    for k, (con_i, sign, _) in enumerate(slack_info):
        partial[con_i, n_vars + k] = sign

    # Natural basis detection
    basis_name, _ = _find_natural_basis(partial, m, n_pre_art, pre_var_names)

    # Artificial variables for rows without natural basis
    art_info = []
    a_count  = 1
    for i in range(m):
        if i not in basis_name:
            art_info.append((i, f"a{a_count}"))
            a_count += 1

    n_art         = len(art_info)
    art_col_start = n_pre_art
    var_names     = pre_var_names + [av[1] for av in art_info]
    has_phase1    = n_art > 0

    # Number of objective rows: 2 if Phase-1 needed, else 1
    n_obj_rows = 2 if has_phase1 else 1
    total_cols = n_pre_art + n_art + 1          # +1 for RHS
    tableau    = np.zeros((n_obj_rows + m, total_cols), dtype=float)

    # ── Original objective row ────────────────────────────────────────────
    orig_obj_row = 1 if has_phase1 else 0

    objective_internal = [(-float(c) if goal_norm == "min" else float(c)) for c in objective]
    for j, c in enumerate(objective_internal):
        # Objective row stores -c_j under internal max convention.
        tableau[orig_obj_row, j] = -float(c)

    # ── Constraint rows ──────────────────────────────────────────────────
    con_offset = n_obj_rows          # first constraint row index
    for i, row in enumerate(constraints):
        ri = con_offset + i
        for j in range(n_vars):
            tableau[ri, j] = float(row[j])
        tableau[ri, -1] = float(row[n_vars])

    # Slack / surplus columns
    for k, (con_i, sign, _) in enumerate(slack_info):
        tableau[con_offset + con_i, n_vars + k] = sign

    # Artificial columns
    for k, (con_i, _) in enumerate(art_info):
        tableau[con_offset + con_i, art_col_start + k] = 1.0

    # ── Build initial basis ──────────────────────────────────────────────
    art_map = {con_i: name for con_i, name in art_info}
    basis   = []
    for i in range(m):
        basis.append(basis_name.get(i) or art_map[i])

    # ── Canonicalize objective rows ──────────────────────────────────────
    if has_phase1:
        # Phase-1 objective: max W = −Σ a_i  ⟹  row 0 stores +1 for each a_i
        for k in range(n_art):
            tableau[0, art_col_start + k] = 1.0
        # Eliminate basis columns from Phase-1 row
        for i, bv in enumerate(basis):
            col    = var_names.index(bv)
            factor = tableau[0, col]
            if abs(factor) > EPS_OPT:
                tableau[0] -= factor * tableau[con_offset + i]

    # Eliminate basis columns from original objective row
    for i, bv in enumerate(basis):
        col    = var_names.index(bv)
        factor = tableau[orig_obj_row, col]
        if abs(factor) > EPS_OPT:
            tableau[orig_obj_row] -= factor * tableau[con_offset + i]

    return {
        "tableau"      : tableau,
        "basis"        : basis,
        "var_names"    : var_names,
        "has_phase1"   : has_phase1,
        "art_col_start": art_col_start,
        "n_art"        : n_art,
        "goal"         : goal_norm,
        "objective_internal": objective_internal,
        "n_decision_vars": len(base_var_names),
        "decision_var_names": base_var_names,
    }
