import numpy as np

try:
    from .stage3_full_tableau import (
        check_optimal,
        choose_pivot,
        pivot_operation,
        run_full_tableau_with_snapshots,
    )
except ImportError:
    from algorithms.stage3_full_tableau import (
        check_optimal,
        choose_pivot,
        pivot_operation,
        run_full_tableau_with_snapshots,
    )

try:
    from .stage4_bland_rules import choose_entering_bland, choose_leaving_bland
except ImportError:
    from algorithms.stage4_bland_rules import choose_entering_bland, choose_leaving_bland

try:
    from ..utils.numeric_policy import EPS_OPT, EPS_PIV
except ImportError:
    from utils.numeric_policy import EPS_OPT, EPS_PIV


def _basis_cols_from_names(basis, var_names):
    cols = []
    for name in basis:
        if name not in var_names:
            return None
        cols.append(var_names.index(name))
    return cols


def _identity_basis_cols(A):
    m, n = A.shape
    basis_cols = [None] * m
    used_cols = set()

    for col in range(n):
        col_vec = A[:, col]
        nz = np.where(np.abs(col_vec) > EPS_OPT)[0]
        if len(nz) != 1:
            continue
        r = int(nz[0])
        if abs(col_vec[r] - 1.0) > EPS_OPT:
            continue
        if basis_cols[r] is None and col not in used_cols:
            basis_cols[r] = col
            used_cols.add(col)

    if any(c is None for c in basis_cols):
        return None
    return [int(c) for c in basis_cols]


def _build_cost_vector(var_names, objective_internal, n_decision_vars):
    c = np.zeros(len(var_names), dtype=float)
    cap = min(len(objective_internal), n_decision_vars, len(var_names))
    for j in range(cap):
        c[j] = float(objective_internal[j])
    return c


def _extract_solution_map(var_names, basis_cols, x_B):
    x = np.zeros(len(var_names), dtype=float)
    for i, col in enumerate(basis_cols):
        x[col] = float(x_B[i])
    x[np.abs(x) <= EPS_OPT] = 0.0
    return {name: float(x[i]) for i, name in enumerate(var_names)}


def _build_solution_vector(n_vars, basis_cols, x_B):
    x = np.zeros(n_vars, dtype=float)
    for i, col in enumerate(basis_cols):
        x[col] = float(x_B[i])
    x[np.abs(x) <= EPS_OPT] = 0.0
    return x


def _build_sensitivity_report(A, b, c, var_names, x_vec, y_vec):
    reduced_costs = {}
    for j, name in enumerate(var_names):
        rc = float(c[j] - y_vec @ A[:, j])
        reduced_costs[name] = 0.0 if abs(rc) <= EPS_OPT else rc

    dual_prices = {
        f"row_{i+1}": (0.0 if abs(float(v)) <= EPS_OPT else float(v))
        for i, v in enumerate(y_vec)
    }

    slacks = b - A @ x_vec
    binding_constraints = [i + 1 for i, s in enumerate(slacks) if abs(float(s)) <= 1e-8]

    return {
        "reduced_costs": reduced_costs,
        "dual_prices": dual_prices,
        "binding_constraints": binding_constraints,
    }


def _stable_solve(B, rhs, transpose=False):
    """Solve Bx=rhs (or B^T x=rhs) with guarded fallback for ill-conditioned bases."""
    M = B.T if transpose else B
    try:
        sol = np.linalg.solve(M, rhs)
        residual = np.linalg.norm(M @ sol - rhs, ord=np.inf)
        if not np.isfinite(residual) or residual > 1e-7:
            raise np.linalg.LinAlgError("high_residual")
        return sol
    except np.linalg.LinAlgError:
        # Least-squares fallback is more stable than explicit inversion for near-singular bases.
        sol, _, _, _ = np.linalg.lstsq(M, rhs, rcond=None)
        residual = np.linalg.norm(M @ sol - rhs, ord=np.inf)
        if not np.isfinite(residual) or residual > 1e-5:
            return None
        return sol


def _compact_from_steps(steps, goal):
    if not steps:
        return {
            "status": "not_implemented",
            "solution_map": {},
            "objective_value": None,
            "iterations": 0,
            "termination_reason": "empty_steps",
            "engine": "full_tableau_fallback",
            "sensitivity": None,
        }

    final = steps[-1]
    label = final.get("step_name", "")
    status_map = {
        "Nghiệm tối ưu": "optimal",
        "Không bị chặn": "unbounded",
        "Vô nghiệm": "infeasible",
    }
    status = status_map.get(label, "not_implemented")

    iterations = sum(1 for s in steps if s.get("pivot_row") is not None)
    result = {
        "status": status,
        "solution_map": {},
        "objective_value": None,
        "iterations": iterations,
        "termination_reason": label or "terminal_step",
        "engine": "full_tableau_fallback",
        "sensitivity": None,
    }

    if status != "optimal":
        return result

    tableau = np.asarray(final.get("tableau"), dtype=float)
    basis = list(final.get("basis", []))
    var_names = list(final.get("var_names", []))

    sol = {name: 0.0 for name in var_names}
    for i, bname in enumerate(basis, start=1):
        if i < tableau.shape[0] and bname in sol:
            sol[bname] = float(tableau[i, -1])

    obj = float(tableau[0, -1])
    if goal == "min":
        obj = -obj

    result["solution_map"] = sol
    result["objective_value"] = obj
    return result


def _prepare_phase2_tableau(standard_system, max_iter=400):
    tableau = np.array(standard_system["tableau"], dtype=float, copy=True)
    basis = list(standard_system["basis"])
    var_names = list(standard_system["var_names"])

    if not standard_system.get("has_phase1"):
        return {
            "status": "ok",
            "phase2_tableau": tableau,
            "var_names": var_names,
            "basis_cols": _basis_cols_from_names(basis, var_names),
            "termination_reason": "no_phase1",
        }

    con_off = 2
    for _ in range(max_iter):
        is_opt, pcol, _, _ = check_optimal(tableau, obj_row_idx=0)
        if is_opt:
            if abs(tableau[0, -1]) > 1e-8:
                return {
                    "status": "infeasible",
                    "termination_reason": "phase1_positive_w",
                }
            break

        prow, _, _, _ = choose_pivot(
            tableau,
            pcol,
            first_con_row=con_off,
            basis=basis,
            var_names=var_names,
        )
        if prow is None:
            return {
                "status": "infeasible",
                "termination_reason": "phase1_no_valid_pivot",
            }

        tableau = pivot_operation(tableau, prow, pcol)
        basis[prow - con_off] = var_names[pcol]
    else:
        return {
            "status": "iteration_limit",
            "termination_reason": "phase1_iteration_limit",
        }

    art_col_start = int(standard_system["art_col_start"])
    n_art = int(standard_system["n_art"])
    keep_cols = [
        c for c in range(tableau.shape[1])
        if c < art_col_start or c >= art_col_start + n_art
    ]

    phase2_tableau = tableau[1:, :][:, keep_cols]
    phase2_var_names = [var_names[c] for c in keep_cols[:-1]]

    A2 = phase2_tableau[1:, :-1]
    basis_cols = _identity_basis_cols(A2)
    if basis_cols is None:
        return {
            "status": "fallback",
            "termination_reason": "phase2_basis_recovery_failed",
        }

    return {
        "status": "ok",
        "phase2_tableau": phase2_tableau,
        "var_names": phase2_var_names,
        "basis_cols": basis_cols,
        "termination_reason": "phase1_complete",
    }


def _solve_revised_phase2(A, b, c, var_names, basis_cols, max_iter=800):
    m, n = A.shape
    basis_cols = [int(cidx) for cidx in basis_cols]

    if len(basis_cols) != m:
        return {
            "status": "numerical_error",
            "solution_map": {},
            "objective_value": None,
            "iterations": 0,
            "termination_reason": "basis_size_mismatch",
            "engine": "revised_simplex",
            "sensitivity": None,
        }

    iterations = 0
    for _ in range(max_iter):
        B = A[:, basis_cols]
        x_B = _stable_solve(B, b)
        if x_B is None:
            return {
                "status": "numerical_error",
                "solution_map": {},
                "objective_value": None,
                "iterations": iterations,
                "termination_reason": "singular_basis",
                "engine": "revised_simplex",
                "sensitivity": None,
            }

        x_B[np.abs(x_B) <= EPS_OPT] = 0.0

        c_B = c[basis_cols]
        y = _stable_solve(B, c_B, transpose=True)
        if y is None:
            return {
                "status": "numerical_error",
                "solution_map": {},
                "objective_value": None,
                "iterations": iterations,
                "termination_reason": "dual_solve_failed",
                "engine": "revised_simplex",
                "sensitivity": None,
            }

        basis_set = set(basis_cols)
        improving = []
        best_rc = 0.0
        for j in range(n):
            if j in basis_set:
                continue
            rc = float(c[j] - y @ A[:, j])
            if rc > EPS_OPT:
                improving.append((j, rc))
                if rc > best_rc:
                    best_rc = rc

        if not improving:
            objective_value = float(c_B @ x_B)
            x_vec = _build_solution_vector(n, basis_cols, x_B)
            return {
                "status": "optimal",
                "solution_map": _extract_solution_map(var_names, basis_cols, x_B),
                "objective_value": objective_value,
                "iterations": iterations,
                "termination_reason": "optimality_reached",
                "engine": "revised_simplex",
                "sensitivity": _build_sensitivity_report(A, b, c, var_names, x_vec, y),
            }

        entering_candidates = [j for j, rc in improving if abs(rc - best_rc) <= EPS_OPT]
        entering_col = choose_entering_bland(entering_candidates)

        d = _stable_solve(B, A[:, entering_col])
        if d is None:
            return {
                "status": "numerical_error",
                "solution_map": {},
                "objective_value": None,
                "iterations": iterations,
                "termination_reason": "direction_solve_failed",
                "engine": "revised_simplex",
                "sensitivity": None,
            }
        if np.all(d <= EPS_PIV):
            return {
                "status": "unbounded",
                "solution_map": {},
                "objective_value": None,
                "iterations": iterations,
                "termination_reason": f"no_positive_direction_for_{var_names[entering_col]}",
                "engine": "revised_simplex",
                "sensitivity": None,
            }

        ratio_candidates = []
        for i in range(m):
            if d[i] > EPS_PIV:
                ratio = float(x_B[i] / d[i])
                if ratio >= -EPS_OPT:
                    ratio_candidates.append((i, 0.0 if abs(ratio) <= EPS_OPT else ratio))

        if not ratio_candidates:
            return {
                "status": "unbounded",
                "solution_map": {},
                "objective_value": None,
                "iterations": iterations,
                "termination_reason": "ratio_test_failed",
                "engine": "revised_simplex",
                "sensitivity": None,
            }

        min_ratio = min(r for _, r in ratio_candidates)
        tie_rows = [i for i, r in ratio_candidates if abs(r - min_ratio) <= EPS_OPT]

        if len(tie_rows) > 1:
            basis_names = [var_names[cidx] for cidx in basis_cols]
            leave_pos = choose_leaving_bland(
                tie_rows,
                basis_names,
                var_names,
                first_con_row=0,
            )
            if leave_pos is None:
                leave_pos = min(tie_rows)
        else:
            leave_pos = tie_rows[0]

        basis_cols[leave_pos] = entering_col
        iterations += 1

    return {
        "status": "iteration_limit",
        "solution_map": {},
        "objective_value": None,
        "iterations": iterations,
        "termination_reason": "phase2_iteration_limit",
        "engine": "revised_simplex",
        "sensitivity": None,
    }


def run_revised_simplex(standard_system):
    """Stage 5 production solver.

    Uses revised simplex on Phase-2 representation and returns compact output.
    Falls back to the full-tableau engine only when a stable revised start basis
    cannot be reconstructed.
    """
    goal = standard_system.get("goal", "max")

    prep = _prepare_phase2_tableau(standard_system)
    if prep["status"] in {"infeasible", "iteration_limit"}:
        return {
            "status": prep["status"],
            "solution_map": {},
            "objective_value": None,
            "iterations": 0,
            "termination_reason": prep["termination_reason"],
            "engine": "revised_simplex",
            "sensitivity": None,
        }

    if prep["status"] == "fallback":
        steps = run_full_tableau_with_snapshots(standard_system)
        result = _compact_from_steps(steps, goal)
        result["termination_reason"] = prep["termination_reason"]
        return result

    phase2_tableau = prep["phase2_tableau"]
    var_names = prep["var_names"]
    basis_cols = prep["basis_cols"]

    if basis_cols is None:
        steps = run_full_tableau_with_snapshots(standard_system)
        return _compact_from_steps(steps, goal)

    A = np.asarray(phase2_tableau[1:, :-1], dtype=float)
    b = np.asarray(phase2_tableau[1:, -1], dtype=float)

    objective_internal = standard_system.get("objective_internal", [])
    n_decision_vars = int(standard_system.get("n_decision_vars", len(objective_internal)))
    c = _build_cost_vector(var_names, objective_internal, n_decision_vars)

    result = _solve_revised_phase2(A, b, c, var_names, basis_cols)

    if result["status"] == "optimal" and result["objective_value"] is not None and goal == "min":
        result["objective_value"] = -float(result["objective_value"])

    return result
