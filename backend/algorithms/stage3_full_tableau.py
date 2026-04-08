import numpy as np

try:
    from .stage4_bland_rules import choose_entering_bland, choose_leaving_bland
except ImportError:
    from stage4_bland_rules import choose_entering_bland, choose_leaving_bland

try:
    from ..utils.numeric_policy import EPS_OPT, EPS_PIV
except ImportError:
    from utils.numeric_policy import EPS_OPT, EPS_PIV

def check_optimal(tableau, obj_row_idx=0):
    obj_row = tableau[obj_row_idx, :-1]
    min_val = obj_row.min()
    if min_val >= -EPS_OPT:
        return True, None, False, []

    candidates = [j for j, v in enumerate(obj_row) if v <= min_val + EPS_OPT]
    pivot_col = choose_entering_bland(candidates)
    return False, pivot_col, len(candidates) > 1, candidates

def choose_pivot(tableau, pivot_col, first_con_row=1, basis=None, var_names=None):
    m = tableau.shape[0] - first_con_row
    ratios = []
    valid = []

    for i in range(first_con_row, first_con_row + m):
        a = tableau[i, pivot_col]
        b = tableau[i, -1]
        if a <= EPS_PIV:
            ratios.append(None)
        else:
            r = float(b / a)
            if r < -EPS_OPT:
                ratios.append(None)
                continue

            r = 0.0 if abs(r) <= EPS_OPT else r
            ratios.append(r)
            valid.append((i, r))

    if not valid:
        return None, ratios, False, []

    min_ratio = min(r for _, r in valid)
    tie_rows = [row_idx for row_idx, r in valid if abs(r - min_ratio) <= EPS_OPT]

    if len(tie_rows) == 1:
        return tie_rows[0], ratios, False, tie_rows

    if basis is None or var_names is None:
        return min(tie_rows), ratios, True, tie_rows

    pivot_row = choose_leaving_bland(tie_rows, basis, var_names, first_con_row=first_con_row)
    return pivot_row, ratios, True, tie_rows

def pivot_operation(tableau, pivot_row, pivot_col):
    t = tableau.astype(float, copy=True)
    piv = t[pivot_row, pivot_col]
    t[pivot_row] /= piv
    for i in range(t.shape[0]):
        if i != pivot_row:
            t[i] -= t[i, pivot_col] * t[pivot_row]
    return t

def yield_tableau_snapshot(step_name, tableau, basis, pivot_row, pivot_col, ratios, explanation, var_names, phase):
    """
    Hàm chuẩn hóa Snapshot để push 1 vòng lặp cho UI render.
    """
    # Gỡ bỏ các giá trị np.nan khỏi mảng ratios (chuyển thành None cho JSON)
    clean_ratios = [None if r is None or np.isnan(r) else r for r in ratios] if ratios else None
    
    return {
        "step_name": step_name,
        "tableau": tableau.tolist() if hasattr(tableau, 'tolist') else tableau,
        "basis": list(basis),
        "pivot_row": pivot_row,
        "pivot_col": pivot_col,
        "ratios": clean_ratios,
        "explanation": explanation,
        "phase": phase,
        "var_names": list(var_names)
    }

def run_full_tableau_with_snapshots(init_dict):
    """
    STAGE 3: Nhận input chuẩn hóa, chạy Loop Tableau và trả về mảng `steps`.
    """
    MAX_ITER      = 200
    tableau       = init_dict["tableau"].copy()
    basis         = list(init_dict["basis"])
    var_names     = list(init_dict["var_names"])
    has_phase1    = init_dict["has_phase1"]
    art_col_start = init_dict["art_col_start"]
    n_art         = init_dict["n_art"]

    steps = []

    def _snap(step_name, tab, bas, pr, pc, rats, expl, vn=None, phase=2):
        full_tab = tab.copy()
        
        # Determine internal display tableau logic
        if has_phase1 and full_tab.shape[0] > len(bas) + 1:
            disp_tab = np.vstack([full_tab[1:2], full_tab[2:]])
            if phase == 1:
                # for phase 1 we might want to attach phase1_tab
                disp_tab = np.vstack([full_tab[0:1], full_tab[2:]])
        else:
            disp_tab = full_tab
            
        steps.append(yield_tableau_snapshot(
            step_name, disp_tab, bas, pr, pc, rats, expl, vn or var_names, phase
        ))

    con_off = 2 if has_phase1 else 1

    # PHASE 1
    if has_phase1:
        _snap("Pha 1 — Bảng ban đầu", tableau, basis, None, None, None, "Phase 1: minimise sum of artificial variables to find a BFS.", phase=1)

        for it in range(1, MAX_ITER + 1):
            is_opt, pcol, enter_tie, enter_candidates = check_optimal(tableau, obj_row_idx=0)
            if is_opt:
                w_val = tableau[0, -1]
                if abs(w_val) > 1e-8:
                    _snap("Vô nghiệm", tableau, basis, None, None, None, "Phase 1 optimal value ≠ 0 → problem is infeasible.", phase=1)
                    return steps
                break

            prow, rats, leave_tie, leave_candidates = choose_pivot(
                tableau,
                pcol,
                first_con_row=con_off,
                basis=basis,
                var_names=var_names,
            )
            if prow is None:
                _snap("Không bị chặn (Pha 1)", tableau, basis, None, pcol, rats, f"Column {var_names[pcol]} unbounded in Phase 1.", phase=1)
                return steps

            entering = var_names[pcol]
            leaving  = basis[prow - con_off]
            disp_prow = prow - con_off + 1

            tie_notes = []
            if enter_tie:
                tie_notes.append(
                    f"Bland tie-break (entering): candidates {enter_candidates} -> chose column {pcol}"
                )
            if leave_tie:
                tie_notes.append(
                    f"Bland tie-break (leaving): candidate rows {leave_candidates} -> chose row {disp_prow}"
                )
            tie_suffix = f" | {'; '.join(tie_notes)}" if tie_notes else ""

            _snap(
                f"Pha 1 — Lần lặp {it}",
                tableau,
                basis,
                disp_prow,
                pcol,
                rats,
                f"Ph1 — Entering: {entering} | Leaving: {leaving} | Pivot: ({prow},{pcol}) = {tableau[prow, pcol]:.4g}{tie_suffix}",
                phase=1,
            )

            tableau = pivot_operation(tableau, prow, pcol)
            basis[prow - con_off] = entering

        _snap("Pha 1 — Kết thúc (BFS khả thi)", tableau, basis, None, None, None, "Phase 1 complete: all artificials = 0. Dropping artificial columns.", phase=1)

        keep_cols = [c for c in range(tableau.shape[1]) if c < art_col_start or c >= art_col_start + n_art]
        tableau   = tableau[1:, :][:, keep_cols]
        var_names = [var_names[c] for c in keep_cols[:-1]]
        con_off      = 1
        has_phase1   = False

    # PHASE 2
    _snap("Bảng ban đầu", tableau, basis, None, None, None, "Starting Phase 2 with the original objective.", var_names)

    for it in range(1, MAX_ITER + 1):
        is_opt, pcol, enter_tie, enter_candidates = check_optimal(tableau, obj_row_idx=0)
        if is_opt:
            infeasible = any(v.startswith("a") and abs(tableau[ri + 1, -1]) > 1e-8 for ri, v in enumerate(basis))
            if infeasible:
                _snap("Vô nghiệm", tableau, basis, None, None, None, "Artificial variable in basis with nonzero value.", var_names)
            else:
                _snap("Nghiệm tối ưu", tableau, basis, None, None, None, "Optimality condition satisfied.", var_names)
            break

        prow, rats, leave_tie, leave_candidates = choose_pivot(
            tableau,
            pcol,
            first_con_row=con_off,
            basis=basis,
            var_names=var_names,
        )
        if prow is None:
            _snap("Không bị chặn", tableau, basis, None, pcol, rats, f"Column {var_names[pcol]} unbounded.", var_names)
            break

        entering = var_names[pcol]
        leaving  = basis[prow - con_off]

        tie_notes = []
        if enter_tie:
            tie_notes.append(
                f"Bland tie-break (entering): candidates {enter_candidates} -> chose column {pcol}"
            )
        if leave_tie:
            tie_notes.append(
                f"Bland tie-break (leaving): candidate rows {leave_candidates} -> chose row {prow}"
            )
        tie_suffix = f" | {'; '.join(tie_notes)}" if tie_notes else ""

        _snap(
            f"Lần lặp {it}",
            tableau,
            basis,
            prow,
            pcol,
            rats,
            f"Entering: {entering} | Leaving: {leaving} | Pivot: ({prow},{pcol}) = {tableau[prow, pcol]:.4g}{tie_suffix}",
            var_names,
        )

        tableau = pivot_operation(tableau, prow, pcol)
        basis[prow - con_off] = entering

    return steps
