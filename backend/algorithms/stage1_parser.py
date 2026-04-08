"""Stage 1 parser and normalizer.

Responsibilities:
- Normalize RHS signs and flip inequality direction when needed.
- Expand unrestricted variables using x = x_plus - x_minus.
- Return metadata that frontend can use to explain normalization.
"""

try:
    from ..utils.numeric_policy import EPS_OPT
except ImportError:
    from utils.numeric_policy import EPS_OPT

CANONICAL_NONNEG = "nonnegative"
CANONICAL_FREE = "free"


def _canonicalize_variable_sign(raw_sign):
    token = str(raw_sign).strip().lower().replace(" ", "")

    nonneg_aliases = {
        "nonnegative",
        "non-negative",
        ">=0",
        "positive",
        "plus",
        "nn",
    }
    free_aliases = {
        "free",
        "unrestricted",
        "urs",
        "any",
        "r",
    }

    if token in free_aliases:
        return CANONICAL_FREE
    if token in nonneg_aliases or token == "":
        return CANONICAL_NONNEG

    raise ValueError(
        f"Unsupported variable sign '{raw_sign}'. Allowed: nonnegative or free."
    )


def _normalize_variable_signs(variable_signs, n_vars):
    if variable_signs is None:
        return [CANONICAL_NONNEG] * n_vars

    if len(variable_signs) != n_vars:
        raise ValueError(
            "Length of variable_signs must match the number of objective coefficients."
        )

    return [_canonicalize_variable_sign(s) for s in variable_signs]


def _expand_unrestricted_variables(objective, constraints, variable_signs):
    expanded_objective = []
    expanded_constraints = [[] for _ in constraints]
    decision_var_names = []
    substitutions = []

    for col, (coef, sign) in enumerate(zip(objective, variable_signs), start=1):
        if sign == CANONICAL_FREE:
            plus_name = f"x{col}_plus"
            minus_name = f"x{col}_minus"

            expanded_objective.extend([float(coef), -float(coef)])
            decision_var_names.extend([plus_name, minus_name])

            for r, row in enumerate(constraints):
                a = float(row[col - 1])
                expanded_constraints[r].extend([a, -a])

            substitutions.append(
                {
                    "original": f"x{col}",
                    "plus": plus_name,
                    "minus": minus_name,
                    "formula": f"x{col} = {plus_name} - {minus_name}",
                }
            )
        else:
            decision_var_names.append(f"x{col}")
            expanded_objective.append(float(coef))

            for r, row in enumerate(constraints):
                expanded_constraints[r].append(float(row[col - 1]))

    return {
        "objective": expanded_objective,
        "constraints": expanded_constraints,
        "decision_var_names": decision_var_names,
        "substitutions": substitutions,
    }


def _is_zero_row(row):
    return all(abs(float(v)) <= EPS_OPT for v in row)


def _row_key(row):
    return tuple(round(float(v), 12) for v in row)


def _presolve_stage1(rows, types, rhs):
    """Apply lightweight Stage-1 presolve: scaling, contradictions, redundancy."""
    removed = []
    scaling = []
    kept = []
    key_to_pos = {}

    for src_row, (row, t, b_val) in enumerate(zip(rows, types, rhs), start=1):
        raw_row = [float(v) for v in row]
        raw_b = float(b_val)

        row_scale = max(abs(v) for v in raw_row) if raw_row else 0.0
        if row_scale > 1.0 + EPS_OPT:
            row_scaled = [v / row_scale for v in raw_row]
            b_scaled = raw_b / row_scale
            scaling.append({"row": src_row, "factor": row_scale})
        else:
            row_scaled = raw_row
            b_scaled = raw_b

        if _is_zero_row(row_scaled):
            if t == "<=" and b_scaled < -EPS_OPT:
                raise ValueError(f"Presolve phát hiện mâu thuẫn tại ràng buộc {src_row}: 0 <= {b_scaled:.6g} là sai.")
            if t == ">=" and b_scaled > EPS_OPT:
                raise ValueError(f"Presolve phát hiện mâu thuẫn tại ràng buộc {src_row}: 0 >= {b_scaled:.6g} là sai.")
            if t == "=" and abs(b_scaled) > EPS_OPT:
                raise ValueError(f"Presolve phát hiện mâu thuẫn tại ràng buộc {src_row}: 0 = {b_scaled:.6g} là sai.")

            removed.append({"row": src_row, "reason": "trivial_always_true"})
            continue

        key = _row_key(row_scaled)
        pos = key_to_pos.get((t, key))
        if pos is None:
            key_to_pos[(t, key)] = len(kept)
            kept.append({"row": row_scaled, "type": t, "rhs": b_scaled, "src": src_row})
            continue

        prev = kept[pos]
        prev_rhs = prev["rhs"]

        if t == "=":
            if abs(prev_rhs - b_scaled) > EPS_OPT:
                raise ValueError(
                    f"Presolve phát hiện mâu thuẫn: hai ràng buộc '=' cùng vế trái nhưng RHS khác nhau "
                    f"(hàng {prev['src']} và {src_row})."
                )
            removed.append({"row": src_row, "reason": "duplicate_equality"})
            continue

        if t == "<=":
            if b_scaled >= prev_rhs - EPS_OPT:
                removed.append({"row": src_row, "reason": "dominated_or_duplicate"})
            else:
                removed.append({"row": prev["src"], "reason": "dominated_by_tighter_bound"})
                kept[pos] = {"row": row_scaled, "type": t, "rhs": b_scaled, "src": src_row}
            continue

        if t == ">=":
            if b_scaled <= prev_rhs + EPS_OPT:
                removed.append({"row": src_row, "reason": "dominated_or_duplicate"})
            else:
                removed.append({"row": prev["src"], "reason": "dominated_by_tighter_bound"})
                kept[pos] = {"row": row_scaled, "type": t, "rhs": b_scaled, "src": src_row}

    bounds = {}
    for item in kept:
        key = _row_key(item["row"])
        entry = bounds.setdefault(key, {"lb": None, "ub": None, "eq": None, "src": []})
        entry["src"].append(item["src"])
        if item["type"] == "<=":
            entry["ub"] = item["rhs"] if entry["ub"] is None else min(entry["ub"], item["rhs"])
        elif item["type"] == ">=":
            entry["lb"] = item["rhs"] if entry["lb"] is None else max(entry["lb"], item["rhs"])
        else:
            entry["eq"] = item["rhs"]

    for key_data in bounds.values():
        lb = key_data["lb"]
        ub = key_data["ub"]
        eq = key_data["eq"]
        rows_ref = key_data["src"]

        if lb is not None and ub is not None and lb > ub + EPS_OPT:
            raise ValueError(
                f"Presolve phát hiện mâu thuẫn: cận dưới lớn hơn cận trên cho cùng vế trái (hàng {rows_ref})."
            )
        if eq is not None and ub is not None and eq > ub + EPS_OPT:
            raise ValueError(
                f"Presolve phát hiện mâu thuẫn: ràng buộc '=' vượt quá cận trên cho cùng vế trái (hàng {rows_ref})."
            )
        if eq is not None and lb is not None and eq < lb - EPS_OPT:
            raise ValueError(
                f"Presolve phát hiện mâu thuẫn: ràng buộc '=' nhỏ hơn cận dưới cho cùng vế trái (hàng {rows_ref})."
            )

    kept_rows = [item["row"] for item in kept]
    kept_types = [item["type"] for item in kept]
    kept_rhs = [item["rhs"] for item in kept]

    return {
        "constraints": kept_rows,
        "types": kept_types,
        "rhs": kept_rhs,
        "meta": {
            "scaling": scaling,
            "removed_constraints": removed,
            "kept_constraints": [item["src"] for item in kept],
        },
    }


def parse_and_validate(objective, constraints, types, rhs, goal, variable_signs=None):
    """Normalize raw LP payload into the internal Stage 2 input contract."""
    n_vars = len(objective)
    normalized_signs = _normalize_variable_signs(variable_signs, n_vars)

    expanded = _expand_unrestricted_variables(objective, constraints, normalized_signs)
    expanded_constraints = expanded["constraints"]

    new_constraints = []
    new_types = []
    new_rhs = []
    rhs_flips = []

    for row_idx, (row, t, b) in enumerate(zip(expanded_constraints, types, rhs), start=1):
        b_val = float(b)
        if b_val < 0:
            # Flip whole row and inequality direction to keep RHS non-negative.
            new_row = [-float(val) for val in row]
            new_b = -b_val
            if t == "<=":
                new_t = ">="
            elif t == ">=":
                new_t = "<="
            else:
                new_t = "="

            rhs_flips.append(
                {
                    "row": row_idx,
                    "original_rhs": b_val,
                    "normalized_rhs": new_b,
                    "original_type": t,
                    "normalized_type": new_t,
                }
            )

            new_constraints.append(new_row)
            new_types.append(new_t)
            new_rhs.append(new_b)
        else:
            new_constraints.append([float(v) for v in row])
            new_types.append(t)
            new_rhs.append(b_val)

    presolve = _presolve_stage1(new_constraints, new_types, new_rhs)
    presolved_constraints = presolve["constraints"]
    presolved_types = presolve["types"]
    presolved_rhs = presolve["rhs"]

    merged_constraints = []
    for row, b_val in zip(presolved_constraints, presolved_rhs):
        merged_constraints.append(row + [b_val])

    return {
        "objective": expanded["objective"],
        "constraints": merged_constraints,
        "types": presolved_types,
        "goal": goal,
        "decision_var_names": expanded["decision_var_names"],
        "normalization": {
            "rhs_flips": rhs_flips,
            "unrestricted_substitutions": expanded["substitutions"],
            "variable_signs": normalized_signs,
            "decision_var_names": expanded["decision_var_names"],
            "presolve": presolve["meta"],
        },
    }
