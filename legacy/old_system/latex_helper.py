"""
latex_helper.py
---------------
Utility functions that convert Simplex data to LaTeX strings.
No UI or engine dependencies.
"""

import numpy as np
import re


# ── Internal helper ───────────────────────────────────────────────────────

def _var_label(name: str) -> str:
    """
    Convert a plain variable name to a LaTeX subscript form.
    'x1' → 'x_{1}',  's2' → 's_{2}',  'x12' → 'x_{12}'
    Names with no trailing digits are returned unchanged.
    Returns '?' for None values.
    """
    if name is None:
        return r"\text{?}"
    # Handle names like x1_plus / x1_minus in a math-friendly way.
    m = re.fullmatch(r"([A-Za-z]+)(\d+)(?:_(plus|minus))?", str(name))
    if m:
        letter, index, suffix = m.group(1), m.group(2), m.group(3)
        if suffix == "plus":
            return rf"{letter}_{{{index}}}^{{+}}"
        if suffix == "minus":
            return rf"{letter}_{{{index}}}^{{-}}"
        return rf"{letter}_{{{index}}}"

    for i, ch in enumerate(name):
        if ch.isdigit():
            letter = name[:i]
            index  = name[i:].replace("_", r"\_")
            return rf"{letter}_{{{index}}}"
    return name


def _coeff_term(coeff: float, var_label: str, is_first: bool) -> str:
    """
    Format one term of a linear expression, e.g. '+ 4x_{2}' or '5x_{1}'.

    Rules:
    - coefficient 1  → show only the variable (no '1')
    - coefficient -1 → show '-variable'
    - is_first=True  → no leading '+'
    """
    c = coeff
    if c == 0:
        return ""

    abs_c = abs(c)
    if c < 0:
        sign = "-" if is_first else "- "
    else:
        sign = "" if is_first else "+ "

    if abs_c == 1:
        coeff_str = ""
    elif abs_c == int(abs_c):
        coeff_str = str(int(abs_c))
    else:
        coeff_str = f"{abs_c:g}"

    return f"{sign}{coeff_str}{var_label}"


# ── Public API ────────────────────────────────────────────────────────────

def format_objective(coeffs, var_names, goal: str) -> str:
    """
    Build a LaTeX string for the objective function.

    Parameters
    ----------
    coeffs    : list[float]  e.g. [5, 4]
    var_names : list[str]    e.g. ["x1", "x2"]
    goal      : str          "max" or "min"

    Returns
    -------
    str  e.g. r"\\max Z = 5x_{1} + 4x_{2}"

    Example
    -------
    >>> format_objective([5, 4], ["x1", "x2"], "max")
    '\\\\max Z = 5x_{1} + 4x_{2}'
    """
    goal_cmd = r"\max" if goal == "max" else r"\min"
    terms = []
    for i, (c, name) in enumerate(zip(coeffs, var_names)):
        term = _coeff_term(float(c), _var_label(name), is_first=(len(terms) == 0))
        if term:
            terms.append(term)

    expr = " ".join(terms) if terms else "0"
    return rf"{goal_cmd} Z = {expr}"


def format_w_objective(art_var_names) -> str:
    """
    Build a LaTeX string for the Phase-1 artificial objective.

    Returns e.g. r"\\min W = a_{1} + a_{2}"
    """
    terms = " + ".join(_var_label(v) for v in art_var_names)
    return rf"\min W = {terms}" if terms else r"\min W = 0"


def format_standard_form(tableau, var_names, basis) -> list:
    """
    Build LaTeX strings for each constraint row of the (augmented) tableau.

    The function reads rows 1..m (skipping row 0 which is the objective),
    and skips the last column (RHS) when building the LHS expression.

    Parameters
    ----------
    tableau   : np.ndarray  shape (m+1, n_vars+n_slack+1)
    var_names : list[str]   column-aligned variable names (excluding RHS)
    basis     : list[str]   current basic variable names (one per row 1..m)

    Returns
    -------
    list[str]  one LaTeX equation string per constraint row
               e.g. ['6x_{1} + 4x_{2} + s_{1} = 24', ...]
    """
    t = np.array(tableau, dtype=float)
    m = t.shape[0] - 1   # number of constraint rows

    equations = []
    for i in range(1, m + 1):
        row = t[i]
        rhs = row[-1]
        lhs_parts = []

        for j, name in enumerate(var_names):
            c = row[j]
            term = _coeff_term(c, _var_label(name), is_first=(len(lhs_parts) == 0))
            if term:
                lhs_parts.append(term)

        lhs = " ".join(lhs_parts) if lhs_parts else "0"
        rhs_str = str(int(rhs)) if rhs == int(rhs) else f"{rhs:g}"
        equations.append(rf"{lhs} = {rhs_str}")

    return equations


def format_pivot_choice(pivot_row, pivot_col, var_names, basis, ratios,
                        tableau) -> list:
    """
    Build two LaTeX strings explaining the pivot selection.

    Parameters
    ----------
    pivot_row : int          — 1-based row index of leaving variable
    pivot_col : int          — 0-based column index of entering variable
    var_names : list[str]    — all variable names (column order)
    basis     : list[str]    — current basic variables (row 1..m)
    ratios    : list         — ratio values aligned to constraint rows;
                               None entries mark skipped rows
    tableau   : np.ndarray   — current tableau (before pivot)

    Returns
    -------
    list[str]  two LaTeX strings:
        [0]  entering-variable explanation
        [1]  leaving-variable explanation
    """
    t = np.array(tableau, dtype=float)
    entering = _var_label(var_names[pivot_col])
    leaving  = _var_label(basis[pivot_row - 1])   # pivot_row is 1-based

    obj_coeff = t[0, pivot_col]
    obj_str   = f"{obj_coeff:g}"

    # Determine direction label
    direction_text = "âm nhất" if obj_coeff < 0 else "dương nhất"

    line1 = (
        rf"\text{{Biến vào: }} {entering}"
        rf" \text{{ (cột {pivot_col}, }} C = {obj_str}"
        rf" \text{{ {direction_text})}}"
    )

    # Build ratio explanation: b_i / a_i for the chosen row
    a_piv = t[pivot_row, pivot_col]
    b_piv = t[pivot_row, -1]
    a_str = f"{a_piv:g}"
    b_str = f"{b_piv:g}"

    valid = [r for r in ratios if r is not None]
    min_ratio = min(valid) if valid else None
    min_str   = f"{min_ratio:g}" if min_ratio is not None else "?"

    line2 = (
        rf"\text{{Biến ra: }} {leaving}"
        rf" \text{{ (ratio }} {b_str}/{a_str} = {min_str} \text{{ nhỏ nhất)}}"
    )

    return [line1, line2]


def format_updated_equations(tableau, var_names, basis,
                             highlight_row=None, highlight_col=None) -> list:
    """
    Like format_standard_form but optionally wraps the pivot element in
    \\boxed{} to highlight it.

    Parameters
    ----------
    tableau       : np.ndarray
    var_names     : list[str]
    basis         : list[str]
    highlight_row : int | None  — 1-based row to highlight (pivot row)
    highlight_col : int | None  — 0-based col to highlight (pivot col)

    Returns
    -------
    list[str]  one LaTeX equation string per constraint row
    """
    t = np.array(tableau, dtype=float)
    m = t.shape[0] - 1

    equations = []
    for i in range(1, m + 1):
        row = t[i]
        rhs = row[-1]
        lhs_parts = []

        for j, name in enumerate(var_names):
            c = row[j]
            label = _var_label(name)

            # Insert \boxed{} around the pivot coefficient×variable
            if i == highlight_row and j == highlight_col and c != 0:
                abs_c = abs(c)
                if abs_c == int(abs_c):
                    coeff_str = str(int(abs_c))
                else:
                    coeff_str = f"{abs_c:g}"

                coeff_str = "1" if abs_c == 1 else coeff_str
                sign = "-" if c < 0 else ("" if not lhs_parts else "+ ")
                lhs_parts.append(rf"{sign}\boxed{{{coeff_str}{label}}}")
                continue

            term = _coeff_term(c, label, is_first=(len(lhs_parts) == 0))
            if term:
                lhs_parts.append(term)

        lhs = " ".join(lhs_parts) if lhs_parts else "0"
        rhs_str = str(int(rhs)) if rhs == int(rhs) else f"{rhs:g}"
        equations.append(rf"{lhs} = {rhs_str}")

    return equations


# ── Self-test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # --- format_objective ---
    obj = format_objective([5, 4], ["x1", "x2"], "max")
    print("Objective:", obj)
    assert obj == r"\max Z = 5x_{1} + 4x_{2}", f"Got: {obj}"

    obj_min = format_objective([1, -2, 3], ["x1", "x2", "x3"], "min")
    print("Min obj:  ", obj_min)
    assert obj_min == r"\min Z = x_{1} - 2x_{2} + 3x_{3}", f"Got: {obj_min}"

    # --- format_standard_form ---
    tableau = np.array([
        [-5., -4.,  0.,  0.,  0.],
        [ 6.,  4.,  1.,  0., 24.],
        [ 1.,  2.,  0.,  1.,  6.],
    ])
    var_names = ["x1", "x2", "s1", "s2"]
    basis     = ["s1", "s2"]

    eqs = format_standard_form(tableau, var_names, basis)
    for eq in eqs:
        print("Constraint:", eq)

    assert eqs[0] == r"6x_{1} + 4x_{2} + s_{1} = 24", f"Got: {eqs[0]}"
    assert eqs[1] == r"x_{1} + 2x_{2} + s_{2} = 6",   f"Got: {eqs[1]}"

    print("\nAll format_standard_form assertions passed.")

    # --- format_pivot_choice ---
    # Iteration 1: pivot_row=1, pivot_col=0, entering=x1, leaving=s1
    # ratios = [4.0, 6.0]
    pivot_lines = format_pivot_choice(
        pivot_row=1, pivot_col=0,
        var_names=var_names, basis=basis,
        ratios=[4.0, 6.0], tableau=tableau,
    )
    for line in pivot_lines:
        print("Pivot:", line)
    assert r"x_{1}" in pivot_lines[0], "entering var missing"
    assert r"s_{1}" in pivot_lines[1], "leaving var missing"
    assert "4"      in pivot_lines[1], "min ratio missing"

    print("\nAll format_pivot_choice assertions passed.")

    # --- format_updated_equations ---
    from simplex_engine import pivot_operation
    t_after = pivot_operation(tableau, 1, 0)
    updated = format_updated_equations(
        t_after, var_names, ["x1", "s2"],
        highlight_row=1, highlight_col=0,
    )
    for eq in updated:
        print("Updated:", eq)
    # Pivot element (row 1, col 0) = 1 after normalisation → \boxed{1x_{1}}
    assert r"\boxed{" in updated[0], "boxed highlight missing"

    print("\nAll format_updated_equations assertions passed.")
