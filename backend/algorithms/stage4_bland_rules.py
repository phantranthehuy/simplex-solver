"""Bland tie-break utilities used by Stage 3 and Stage 5.

These helpers keep pivot decisions deterministic when there are ties
in entering or leaving candidates, preventing cycling in degenerate LPs.
"""

from typing import Optional, Sequence


def _basis_name_at_row(row_index: int, basis: Sequence[str], first_con_row: int) -> Optional[str]:
    pos = row_index - first_con_row
    if pos < 0 or pos >= len(basis):
        return None
    return basis[pos]


def _var_order_key(var_name: Optional[str], var_names: Sequence[str]):
    if var_name is None:
        return (10**9, "")
    try:
        return (var_names.index(var_name), var_name)
    except ValueError:
        # Fallback when a name does not appear in var_names.
        digits = "".join(ch for ch in var_name if ch.isdigit())
        return (10**8 + (int(digits) if digits else 0), var_name)


def choose_entering_bland(candidates: Sequence[int]) -> Optional[int]:
    """Return the smallest column index among tied entering candidates."""
    if not candidates:
        return None
    return min(int(c) for c in candidates)


def choose_leaving_bland(
    candidate_rows: Sequence[int],
    basis: Sequence[str],
    var_names: Sequence[str],
    first_con_row: int = 1,
) -> Optional[int]:
    """Return leaving row using Bland's lexical tie-break on basis variable order."""
    if not candidate_rows:
        return None

    rows = [int(r) for r in candidate_rows]
    return min(
        rows,
        key=lambda r: (
            _var_order_key(_basis_name_at_row(r, basis, first_con_row), var_names),
            r,
        ),
    )


def apply_bland_rules(tableau, z_row, constraints_cols):
    """Compatibility shim kept for legacy imports.

    New code should call choose_entering_bland() and choose_leaving_bland().
    """
    del tableau, z_row, constraints_cols
    return None
