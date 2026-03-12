"""
simplex_engine.py
-----------------
Core Simplex algorithm logic — Two-Phase method.  No UI dependencies.
"""

import numpy as np


# ─────────────────────────────────────────────────────────────────────────────
# Helper utilities
# ─────────────────────────────────────────────────────────────────────────────

def _find_natural_basis(partial, m, n_cols, var_names):
    """
    Scan the (m × n_cols) constraint matrix *right-to-left* for unit-vector
    columns that can serve as a natural initial basis.

    Returns
    -------
    basis_name : dict[int, str]   row_idx (0-based) → variable name
    used_cols  : set[int]
    """
    basis_name = {}
    used_cols  = set()
    for col in range(n_cols - 1, -1, -1):
        col_vec      = partial[:, col]
        nonzero_rows = [r for r in range(m) if abs(col_vec[r]) > 1e-10]
        if len(nonzero_rows) == 1:
            r = nonzero_rows[0]
            if (abs(col_vec[r] - 1.0) < 1e-10
                    and r not in basis_name
                    and col not in used_cols):
                basis_name[r] = var_names[col]
                used_cols.add(col)
    return basis_name, used_cols


def standardize(objective, constraints, types, goal):
    """
    Convert an LP to standard (augmented) tableau form.

    Adds slack/surplus for ≤/≥ constraints, and artificial variables
    for rows that lack a natural unit-vector basis column.

    The returned tableau has TWO objective rows when artificials are needed:
        row 0 = Phase-1 objective (min sum of artificials, stored as max −W)
        row 1 = original objective (stored as −c_j for internal max)
        rows 2..m+1 = constraints

    When NO artificials are needed the tableau has ONE objective row:
        row 0 = original objective
        rows 1..m = constraints

    Parameters
    ----------
    objective   : list[float]
    constraints : list[list[float]]  — each row = [a1, a2, ..., rhs]
    types       : list[str]          — "<=", ">=", or "="
    goal        : str                — "max" or "min"

    Returns
    -------
    dict with keys:
        "tableau"      : np.ndarray
        "basis"        : list[str]
        "var_names"    : list[str]     — column-aligned names (excl. RHS)
        "has_phase1"   : bool          — True when artificials are present
        "art_col_start": int           — first artificial column index
        "n_art"        : int           — number of artificial variables
    """
    n_vars = len(objective)
    m      = len(constraints)

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
    pre_var_names = ([f"x{j+1}" for j in range(n_vars)]
                     + [sv[2] for sv in slack_info])

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
    # Stored as −c_j (internal max convention).
    orig_obj_row = 1 if has_phase1 else 0
    for j, c in enumerate(objective):
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
            if abs(factor) > 1e-10:
                tableau[0] -= factor * tableau[con_offset + i]

    # Eliminate basis columns from original objective row
    for i, bv in enumerate(basis):
        col    = var_names.index(bv)
        factor = tableau[orig_obj_row, col]
        if abs(factor) > 1e-10:
            tableau[orig_obj_row] -= factor * tableau[con_offset + i]

    return {
        "tableau"      : tableau,
        "basis"        : basis,
        "var_names"    : var_names,
        "has_phase1"   : has_phase1,
        "art_col_start": art_col_start,
        "n_art"        : n_art,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Core simplex operations
# ─────────────────────────────────────────────────────────────────────────────

def check_optimal(tableau, obj_row_idx=0):
    """
    Check whether objective row `obj_row_idx` satisfies the optimality
    condition for a MAX problem (all reduced costs ≥ 0).

    Returns (is_optimal, pivot_col | None).
    """
    obj_row = tableau[obj_row_idx, :-1]
    min_val = obj_row.min()
    if min_val >= -1e-10:
        return True, None
    return False, int(np.argmin(obj_row))


def choose_pivot(tableau, pivot_col, first_con_row=1):
    """
    Minimum-ratio test.  `first_con_row` is the index of the first
    constraint row in the tableau (1 when 1 obj row, 2 when 2 obj rows).

    Returns (pivot_row | None, ratios).
    """
    m       = tableau.shape[0] - first_con_row
    ratios  = []
    min_ratio = np.inf
    pivot_row = None

    for i in range(first_con_row, first_con_row + m):
        a = tableau[i, pivot_col]
        b = tableau[i, -1]
        if a <= 1e-12:
            ratios.append(None)
        else:
            r = b / a
            ratios.append(r)
            if r < min_ratio - 1e-12:
                min_ratio = r
                pivot_row = i
    return pivot_row, ratios


def pivot_operation(tableau, pivot_row, pivot_col):
    """
    Perform one pivot.  Returns a NEW array (original unchanged).
    """
    t   = tableau.astype(float, copy=True)
    piv = t[pivot_row, pivot_col]
    t[pivot_row] /= piv
    for i in range(t.shape[0]):
        if i != pivot_row:
            t[i] -= t[i, pivot_col] * t[pivot_row]
    return t


# ─────────────────────────────────────────────────────────────────────────────
# Two-Phase Simplex driver
# ─────────────────────────────────────────────────────────────────────────────

def solve_steps(objective, constraints, types, goal):
    """
    Run the Two-Phase Simplex method and record every iteration.

    Phase 1 (only when artificial variables exist):
        Minimise the sum of artificial variables.  If the optimal value
        is 0, we have a basic feasible solution; otherwise infeasible.
        After Phase 1, artificial columns are dropped from the tableau.

    Phase 2:
        Optimise the original objective from the BFS found in Phase 1
        (or directly, if no artificials were needed).

    Returns
    -------
    list[dict]  — one dict per recorded state:
        step_name, tableau, basis, pivot_row, pivot_col, ratios,
        explanation, var_names
    """
    MAX_ITER = 200
    goal     = (goal or "max").lower()

    # Internally always MAX.
    if goal == "min":
        internal_obj = [-float(c) for c in objective]
    else:
        internal_obj = [float(c) for c in objective]

    init          = standardize(internal_obj, constraints, types, "max")
    tableau       = init["tableau"].copy()
    basis         = list(init["basis"])
    var_names     = list(init["var_names"])
    has_phase1    = init["has_phase1"]
    art_col_start = init["art_col_start"]
    n_art         = init["n_art"]
    art_var_names = var_names[art_col_start:art_col_start + n_art] if has_phase1 else []

    steps = []

    # ── Helper: snapshot a step ──────────────────────────────────────────
    def _snap(step_name, tab, bas, pr, pc, rats, expl, vn=None, phase=2):
        """Create a step dict with display tableau(s).

        For Phase 1 steps (phase=1), also stores ``phase1_tab`` which
        contains the W objective row + constraint rows, and ``art_vars``.
        The regular ``tableau`` always uses the Z (original) objective row.
        """
        full_tab = tab.copy()
        step_dict = {
            "step_name" : step_name,
            "_full_tab" : full_tab,
            "basis"     : list(bas),
            "pivot_row" : pr,
            "pivot_col" : pc,
            "ratios"    : rats,
            "explanation": expl,
            "var_names" : list(vn or var_names),
            "phase"     : phase,
        }
        if has_phase1 and full_tab.shape[0] > len(bas) + 1:
            # Internal tableau: row 0 = W (Phase-1 obj), row 1 = Z, rows 2+ = constraints
            step_dict["tableau"] = np.vstack([full_tab[1:2], full_tab[2:]])
            if phase == 1:
                step_dict["phase1_tab"] = np.vstack([full_tab[0:1], full_tab[2:]])
                step_dict["art_vars"] = list(art_var_names)
        else:
            step_dict["tableau"] = full_tab.copy()
        steps.append(step_dict)

    # Offset of first constraint row in the *internal* tableau
    con_off = 2 if has_phase1 else 1

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 1  (only when artificial variables exist)
    # ══════════════════════════════════════════════════════════════════════
    if has_phase1:
        _snap("Pha 1 — Bảng ban đầu", tableau, basis,
              None, None, None,
              "Phase 1: minimise sum of artificial variables to find a BFS.",
              phase=1)

        for it in range(1, MAX_ITER + 1):
            is_opt, pcol = check_optimal(tableau, obj_row_idx=0)
            if is_opt:
                # Phase 1 finished — check feasibility
                w_val = tableau[0, -1]
                if abs(w_val) > 1e-8:
                    _snap("Vô nghiệm", tableau, basis,
                          None, None, None,
                          "Phase 1 optimal value ≠ 0 → problem is infeasible.",
                          phase=1)
                    return steps
                break   # feasible → proceed to Phase 2

            prow, rats = choose_pivot(tableau, pcol, first_con_row=con_off)
            if prow is None:
                _snap("Không bị chặn (Pha 1)", tableau, basis,
                      None, pcol, rats,
                      f"Column {var_names[pcol]} unbounded in Phase 1.",
                      phase=1)
                return steps

            entering = var_names[pcol]
            leaving  = basis[prow - con_off]

            # Display pivot_row as 1-based relative to constraints
            disp_prow = prow - con_off + 1

            _snap(f"Pha 1 — Lần lặp {it}", tableau, basis,
                  disp_prow, pcol, rats,
                  f"Ph1 — Entering: {entering} | Leaving: {leaving} | "
                  f"Pivot: ({prow},{pcol}) = {tableau[prow, pcol]:.4g}",
                  phase=1)

            tableau = pivot_operation(tableau, prow, pcol)
            basis[prow - con_off] = entering

        # Record end of Phase 1
        _snap("Pha 1 — Kết thúc (BFS khả thi)", tableau, basis,
              None, None, None,
              "Phase 1 complete: all artificials = 0.  Dropping artificial "
              "columns and restoring original objective for Phase 2.",
              phase=1)

        # ── Transition: drop artificial columns ──────────────────────────
        # Keep: original-obj row (row 1) + constraint rows (row 2..),
        #       all columns EXCEPT the artificial ones.
        keep_cols = [c for c in range(tableau.shape[1])
                     if c < art_col_start or c >= art_col_start + n_art]
        tableau   = tableau[1:, :][:, keep_cols]   # drop Phase-1 row + art cols
        var_names = [var_names[c] for c in keep_cols[:-1]]  # excl RHS column
        # Reset offsets for Phase 2 (now single obj-row layout)
        con_off      = 1
        has_phase1   = False   # no longer relevant

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 2  (or the only phase if no artificials were needed)
    # ══════════════════════════════════════════════════════════════════════
    _snap("Bảng ban đầu", tableau, basis,
          None, None, None,
          "Starting Phase 2 with the original objective.", var_names)

    for it in range(1, MAX_ITER + 1):
        is_opt, pcol = check_optimal(tableau, obj_row_idx=0)
        if is_opt:
            infeasible = any(
                v.startswith("a") and abs(tableau[ri + 1, -1]) > 1e-8
                for ri, v in enumerate(basis)
            )
            if infeasible:
                _snap("Vô nghiệm", tableau, basis,
                      None, None, None,
                      "Artificial variable in basis with nonzero value.",
                      var_names)
            else:
                _snap("Nghiệm tối ưu", tableau, basis,
                      None, None, None,
                      "Optimality condition satisfied.", var_names)
            break

        prow, rats = choose_pivot(tableau, pcol, first_con_row=con_off)
        if prow is None:
            _snap("Không bị chặn", tableau, basis,
                  None, pcol, rats,
                  f"Column {var_names[pcol]} unbounded.", var_names)
            break

        entering = var_names[pcol]
        leaving  = basis[prow - con_off]

        _snap(f"Lần lặp {it}", tableau, basis,
              prow, pcol, rats,
              f"Entering: {entering} | Leaving: {leaving} | "
              f"Pivot: ({prow},{pcol}) = {tableau[prow, pcol]:.4g}",
              var_names)

        tableau = pivot_operation(tableau, prow, pcol)
        basis[prow - con_off] = entering

    return steps


# ── Self-test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":

    def _extract_solution(steps):
        """Helper: extract (sol_dict, Z_value) from the final step."""
        final   = steps[-1]
        tab     = final["tableau"]
        basis   = final["basis"]
        sol     = {}
        for ri, var in enumerate(basis, start=1):
            sol[var] = round(tab[ri, -1], 6)
        Z = round(tab[0, -1], 6)
        return sol, Z, final

    def _print_steps(steps):
        print("=" * 60)
        for s in steps:
            print(f"  {s['step_name']}  | basis: {s['basis']}")
            print(f"  pivot: row={s['pivot_row']}  col={s['pivot_col']}")
            print(s["tableau"])
            print("  ", s["explanation"])
            print("-" * 60)

    # ── Test 1: All-<= (pure simplex, no artificials) ─────────────────────
    # Max Z = 5x1 + 4x2,  6x1+4x2<=24, x1+2x2<=6
    print("\n*** Test 1: All <= ***")
    steps = solve_steps([5, 4], [[6, 4, 24], [1, 2, 6]], ["<=", "<="], "max")
    _print_steps(steps)
    sol, Z, final = _extract_solution(steps)
    assert final["step_name"] == "Nghiệm tối ưu"
    assert sol.get("x1") == 3.0
    assert sol.get("x2") == 1.5
    assert Z == 21.0
    print("PASS\n")

    # ── Test 2: Natural basis, min problem ────────────────────────────────
    # Min Z = -3x1 - 9x2,  x1+x3=1,  -x1+x2+x4=2
    print("*** Test 2: Natural basis — min ***")
    steps2 = solve_steps([-3, -9, 0, 0],
                         [[1, 0, 1, 0, 1], [-1, 1, 0, 1, 2]],
                         ["=", "="], "min")
    _print_steps(steps2)
    sol2, Z2, final2 = _extract_solution(steps2)
    assert final2["step_name"] == "Nghiệm tối ưu"
    assert sol2.get("x1") == 1.0
    assert sol2.get("x2") == 3.0
    assert Z2 == 30.0
    print("PASS\n")

    # ── Test 3: Two-Phase required (= constraint, no natural basis) ──────
    # Max Z = 3x1 + 3x2 (+2 constant)
    # 4x1 + 2x2 = 4,  5x1 + 3x2 <= 5
    # Expected: x1=1, x2=0, Z'=3
    print("*** Test 3: Two-Phase — = + <= ***")
    steps3 = solve_steps([3, 3], [[4, 2, 4], [5, 3, 5]], ["=", "<="], "max")
    _print_steps(steps3)
    sol3, Z3, final3 = _extract_solution(steps3)
    assert final3["step_name"] == "Nghiệm tối ưu"
    assert sol3.get("x1") == 1.0
    assert Z3 == 3.0
    print("PASS\n")

    # ── Test 4: Natural basis — Min Z = -4x1 - 2x2 (-5 const) ───────────
    # -x1+x2+x3=2,  x1+x4=1
    # Expected: x1=1, x2=3, Z'=-10 → Z=-15
    print("*** Test 4: Natural basis — min ***")
    steps4 = solve_steps([-4, -2, 0, 0],
                         [[-1, 1, 1, 0, 2], [1, 0, 0, 1, 1]],
                         ["=", "="], "min")
    _print_steps(steps4)
    sol4, W4, final4 = _extract_solution(steps4)
    assert final4["step_name"] == "Nghiệm tối ưu"
    assert sol4.get("x1") == 1.0
    assert sol4.get("x2") == 3.0
    Z4 = -W4 - 5
    assert Z4 == -15.0
    print("PASS\n")

    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
