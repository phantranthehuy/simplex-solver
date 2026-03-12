"""
test_qa.py  — Automated QA for Simplex Solver Dash App
Run:  python test_qa.py
"""

import sys, traceback
import numpy as np

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m⚠\033[0m"

results = []

def check(label, condition, notes=""):
    icon = PASS if condition else FAIL
    print(f"  {icon}  {label}" + (f"  — {notes}" if notes else ""))
    results.append((label, condition))


# ─────────────────────────────────────────────────────────────────────────────
# 1. Engine: sample problem  Max Z=5x1+4x2  s.t. 6x1+4x2<=24, x1+2x2<=6
# ─────────────────────────────────────────────────────────────────────────────
print("\n═══ 1. Solver Engine ═══")
from simplex_engine import solve_steps, standardize, check_optimal

objective   = [5, 4]
constraints = [[6, 4, 24], [1, 2, 6]]
types       = ["<=", "<="]
goal        = "max"

init      = standardize(objective, constraints, types, goal)
var_names = init["var_names"]
steps     = solve_steps(objective, constraints, types, goal)

check("var_names == ['x1','x2','s1','s2']", var_names == ["x1","x2","s1","s2"])
check("initial basis == ['s1','s2']",       init["basis"] == ["s1","s2"])

check("step 0 is 'Bảng ban đầu'",  steps[0]["step_name"] == "Bảng ban đầu")
check("step 1 is 'Lần lặp 1'",     steps[1]["step_name"] == "Lần lặp 1")
check("step 2 is 'Lần lặp 2'",     steps[2]["step_name"] == "Lần lặp 2")
check("step 3 is 'Nghiệm tối ưu'", steps[3]["step_name"] == "Nghiệm tối ưu")
check("exactly 4 steps total",     len(steps) == 4)

# Iteration 1: entering x1 (col 0), leaving s1 (row 1), ratios [4,6]
check("iter1 pivot_col==0 (x1 enters)", steps[1]["pivot_col"] == 0)
check("iter1 pivot_row==1 (s1 leaves)", steps[1]["pivot_row"] == 1)
check("iter1 ratios == [4.0, 6.0]",
      steps[1]["ratios"] is not None and
      abs(steps[1]["ratios"][0] - 4.0) < 1e-9 and
      abs(steps[1]["ratios"][1] - 6.0) < 1e-9)

# Iteration 2: entering x2 (col 1), leaving s2 (row 2), ratios [6,1.5]
check("iter2 pivot_col==1 (x2 enters)", steps[2]["pivot_col"] == 1)
check("iter2 pivot_row==2 (s2 leaves)", steps[2]["pivot_row"] == 2)
iter2_ratios = steps[2]["ratios"]
iter2_r0 = round(iter2_ratios[0], 4) if iter2_ratios[0] is not None else None
iter2_r1 = round(iter2_ratios[1], 4) if iter2_ratios[1] is not None else None
check("iter2 ratios ≈ [6.0, 1.5]",
      iter2_r0 is not None and abs(iter2_r0 - 6.0) < 1e-3 and
      iter2_r1 is not None and abs(iter2_r1 - 1.5) < 1e-3,
      f"got [{iter2_r0}, {iter2_r1}]")

# Optimal solution
t_opt = steps[-1]["tableau"]
b_opt = steps[-1]["basis"]
sol = {b_opt[i]: t_opt[i+1, -1] for i in range(len(b_opt))}
Z   = t_opt[0, -1]
check("optimal x1 == 3.0",   abs(sol.get("x1", -1) - 3.0)  < 1e-9, f"x1={sol.get('x1')}")
check("optimal x2 == 1.5",   abs(sol.get("x2", -1) - 1.5)  < 1e-9, f"x2={sol.get('x2')}")
check("optimal Z  == 21.0",  abs(Z - 21.0) < 1e-9,                   f"Z={Z}")


# ─────────────────────────────────────────────────────────────────────────────
# 2. LaTeX helpers
# ─────────────────────────────────────────────────────────────────────────────
print("\n═══ 2. LaTeX Helpers ═══")
from latex_helper import (format_objective, format_standard_form,
                           format_pivot_choice, format_updated_equations,
                           _var_label)
from simplex_engine import pivot_operation

obj_latex = format_objective(objective, var_names[:2], goal)
check(r"objective LaTeX contains \max",  r"\max" in obj_latex)
check("objective has 5x_{1}",            "5x_{1}" in obj_latex)
check("objective has 4x_{2}",            "4x_{2}" in obj_latex)

eqs0 = format_standard_form(steps[0]["tableau"], var_names, steps[0]["basis"])
check("constraint 0 = '6x_{1} + 4x_{2} + s_{1} = 24'",
      eqs0[0] == r"6x_{1} + 4x_{2} + s_{1} = 24", f"got: {eqs0[0]}")
check("constraint 1 = 'x_{1} + 2x_{2} + s_{2} = 6'",
      eqs0[1] == r"x_{1} + 2x_{2} + s_{2} = 6",   f"got: {eqs0[1]}")

plines = format_pivot_choice(1, 0, var_names, steps[0]["basis"],
                              steps[1]["ratios"], steps[0]["tableau"])
check(r"pivot line0 has x_{1} as entering",  r"x_{1}" in plines[0])
check(r"pivot line1 has s_{1} as leaving",   r"s_{1}" in plines[1])
check("pivot line1 shows min ratio 4",       "4" in plines[1])

# After pivot (iter1 → t_after = iter2's tableau)
t_after = steps[2]["tableau"]
updated = format_updated_equations(t_after, var_names, steps[2]["basis"],
                                   highlight_row=1, highlight_col=0)
check("\\boxed present in updated eq0",  r"\boxed{" in updated[0])

# _var_label edge cases
check("_var_label('x1')  == 'x_{1}'",  _var_label("x1")  == "x_{1}")
check("_var_label('s12') == 's_{12}'", _var_label("s12") == "s_{12}")
check("_var_label('Z')   == 'Z'",      _var_label("Z")   == "Z")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Callbacks: serialise / deserialise round-trip
# ─────────────────────────────────────────────────────────────────────────────
print("\n═══ 3. Store Serialisation ═══")
import callbacks as cb

store = cb._serialize_steps(steps, var_names, goal, objective)
check("store has no error",   store["error"] is None)
check("store has 4 steps",    len(store["steps"]) == 4)
check("tableau serialised as list", isinstance(store["steps"][0]["tableau"], list))

steps2 = cb._deserialize_steps(store["steps"])
check("deserialised tableau is ndarray",  isinstance(steps2[0]["tableau"], np.ndarray))
check("round-trip tableau step0 row1[0] == 6.0",
      abs(steps2[0]["tableau"][1, 0] - 6.0) < 1e-9)
check("all numpy values equal after round-trip",
      all(np.allclose(steps[i]["tableau"], steps2[i]["tableau"]) for i in range(4)))


# ─────────────────────────────────────────────────────────────────────────────
# 4. render_algebra_mode — check no exceptions, key text present
# ─────────────────────────────────────────────────────────────────────────────
print("\n═══ 4. render_algebra_mode ═══")
try:
    alg = cb.render_algebra_mode(steps, var_names, goal, objective)
    check("returns a list",         isinstance(alg, list))
    check("non-empty list",         len(alg) > 0)
    alg_str = str(alg)
    check("contains 'Lần lặp 1'",  "L\u1ea7n l\u1eb7p 1" in alg_str)
    check("contains 'tối ưu'",      "t\u1ed1i \u01b0u" in alg_str.lower() or "\u1ed1i \u01b0u" in alg_str)
    check("contains x_{1}",        "x_{1}" in alg_str)
    check("contains Z^{*}",        "Z^{*}" in alg_str or "Z^*" in alg_str)
except Exception as e:
    check("render_algebra_mode no exception", False, str(e))
    traceback.print_exc()


# ─────────────────────────────────────────────────────────────────────────────
# 5. render_table_mode — check no exceptions, correct structure
# ─────────────────────────────────────────────────────────────────────────────
print("\n═══ 5. render_table_mode ═══")
try:
    tbl = cb.render_table_mode(steps, var_names)
    check("returns a list",         isinstance(tbl, list))
    tbl_str = str(tbl)
    check("contains Basis header",  "Basis" in tbl_str)
    check("contains pivot-cell",    "pivot-cell" in tbl_str)
    check("contains ratio-cell",    "ratio-cell" in tbl_str)
    check("contains 21",            "21" in tbl_str, "Z=21 in tableau")
    check("contains 3.00",          "3.00" in tbl_str, "x1=3 value")
    check("contains 1.50",          "1.50" in tbl_str, "x2=1.5 value")
    check("contains min-ratio",     "min-ratio" in tbl_str)
    check("✅ alert present",        "\u2705" in tbl_str, "optimal alert")
except Exception as e:
    check("render_table_mode no exception", False, str(e))
    traceback.print_exc()


# ─────────────────────────────────────────────────────────────────────────────
# 6. render_result callback (Callback 3)
# ─────────────────────────────────────────────────────────────────────────────
print("\n═══ 6. render_result (Callback 3) ═══")
try:
    # None store → placeholder text
    r_none = cb.render_result(None, "algebra")
    r_none_str = str(r_none)
    check("None store → placeholder",  "Gi\u1ea3i" in r_none_str or "k\u1ebft qu\u1ea3" in r_none_str.lower())

    # Error in store
    err_store = {"error": "Test error message", "steps": None}
    r_err = cb.render_result(err_store, "algebra")
    check("error store → Alert",  "Test error message" in str(r_err))

    # Valid store, algebra mode
    r_alg = cb.render_result(store, "algebra")
    check("algebra mode renders without error",  r_alg is not None)

    # Valid store, table mode
    r_tbl = cb.render_result(store, "table")
    check("table mode renders without error",    r_tbl is not None)
    check("table mode differs from algebra",     str(r_alg) != str(r_tbl))
except Exception as e:
    check("render_result no exception", False, str(e))
    traceback.print_exc()


# ─────────────────────────────────────────────────────────────────────────────
# 7. Edge case: Unbounded problem
# ─────────────────────────────────────────────────────────────────────────────
print("\n═══ 7. Edge Case — Unbounded ═══")
try:
    # Max Z = x1+x2 s.t. x1-x2<=1  (unbounded upward in x2)
    ub_steps = solve_steps([1,1], [[1,-1,1]], ["<="], "max")
    last_ub  = ub_steps[-1]["step_name"]
    check("unbounded → last step is 'Không bị chặn'",
          last_ub == "Không bị chặn", f"got: {last_ub}")
    store_ub = cb._serialize_steps(ub_steps,
                                    standardize([1,1],[[1,-1,1]],["<="],"max")["var_names"],
                                    "max", [1,1])
    r_ub = cb.render_result(store_ub, "algebra")
    r_ub_str = str(r_ub)
    check("unbounded → ❌ alert in algebra",  "\u274c" in r_ub_str or "Unbounded" in r_ub_str or "chặn" in r_ub_str)
    r_ub_t = cb.render_result(store_ub, "table")
    r_ub_t_str = str(r_ub_t)
    check("unbounded → ❌ alert in tableau",  "\u274c" in r_ub_t_str or "Unbounded" in r_ub_t_str or "chặn" in r_ub_t_str)
except Exception as e:
    check("unbounded edge case no exception", False, str(e))
    traceback.print_exc()


# ─────────────────────────────────────────────────────────────────────────────
# 8. Edge case: Already optimal at start (all objective coeffs ≥ 0 for min)
# ─────────────────────────────────────────────────────────────────────────────
print("\n═══ 8. Edge Case — Already Optimal at Start ═══")
try:
    # Min Z = x1+x2, only <= constraints → slacks are feasible basis,
    # for min: objective row has +1,+1 which are ≤ 0? No. Let's use
    # a pure Min with all-zero objective (trivially optimal):
    ao_steps = solve_steps([0, 0], [[1,1,4]], ["<="], "min")
    check("zero-objective → already optimal at step 1",
          ao_steps[-1]["step_name"] == "Nghiệm tối ưu")
    check("zero-objective → 2 steps (initial + optimal)",
          len(ao_steps) == 2, f"got {len(ao_steps)} steps")
    store_ao = cb._serialize_steps(ao_steps,
                                    standardize([0,0],[[1,1,4]],["<="],"min")["var_names"],
                                    "min", [0,0])
    r_ao = cb.render_result(store_ao, "algebra")
    check("already-optimal renders without exception", r_ao is not None)
    check("already-optimal: 'ngay từ đầu' or ✅ in output",
          "ngay t\u1eeb \u0111\u1ea7u" in str(r_ao) or "\u2705" in str(r_ao))
except Exception as e:
    check("already-optimal edge case no exception", False, str(e))
    traceback.print_exc()


# ─────────────────────────────────────────────────────────────────────────────
# 9. Edge case: generate_inputs callback with n=1,m=1 and n=10,m=10
# ─────────────────────────────────────────────────────────────────────────────
print("\n═══ 9. Edge Case — generate_inputs boundary values ═══")
try:
    obj1, con1 = cb.generate_inputs(1, 1)
    check("n=1,m=1 returns without error", obj1 is not None and con1 is not None)

    obj10, con10 = cb.generate_inputs(10, 10)
    obj_str = str(obj10)
    con_str = str(con10)
    check("n=10,m=10 returns without error", obj10 is not None and con10 is not None)
    check("n=10 has 10 objective inputs", obj_str.count("obj-coeff") == 10)
    check("m=10 has 10 constraint rows",  con_str.count("con-rhs") == 10)

    # Clamp test: n=0 should be treated as 1, n=11 as 10
    obj_lo, _ = cb.generate_inputs(0, 1)
    check("n=0 clamped to 1", str(obj_lo).count("obj-coeff") == 1)
    obj_hi, _ = cb.generate_inputs(11, 1)
    check("n=11 clamped to 10", str(obj_hi).count("obj-coeff") == 10)
except Exception as e:
    check("generate_inputs no exception", False, str(e))
    traceback.print_exc()


# ─────────────────────────────────────────────────────────────────────────────
# 10. Edge case: run_solver with empty inputs
# ─────────────────────────────────────────────────────────────────────────────
print("\n═══ 10. Edge Case — run_solver validation ═══")
try:
    # No inputs at all (obj_vals=[])
    store_empty, inv_obj, inv_con, inv_rhs = cb.run_solver(
        1, "max", 2, 2, [], [], [], [], None)
    check("empty inputs → error in store",  store_empty.get("error") is not None)
    check("empty inputs → empty invalid lists",  inv_obj == [] and inv_con == [])

    # Missing one coefficient
    store_miss, inv_obj2, _, _ = cb.run_solver(
        1, "max", 2, 1,
        [5, None],        # obj: c2 missing
        [6.0, 4.0],       # con
        ["<="],
        [24.0],
        None,
    )
    check("missing coeff → error in store",   store_miss.get("error") is not None)
    check("missing coeff → obj[1] invalid",   inv_obj2[1] == True if inv_obj2 else False)
except Exception as e:
    check("run_solver validation no exception", False, str(e))
    traceback.print_exc()


# ─────────────────────────────────────────────────────────────────────────────
# 11. LaTeX: fractions rendered as decimals in boxed (known format check)
# ─────────────────────────────────────────────────────────────────────────────
print("\n═══ 11. LaTeX Fraction / Boxed format ═══")
try:
    # After iter1 pivot, row1 coefficients contain fractions
    t2 = steps[2]["tableau"]
    upd = format_updated_equations(t2, var_names, steps[2]["basis"],
                                   highlight_row=2, highlight_col=1)
    check("updated eq has \\boxed",        r"\boxed{" in upd[1])
    # Row 1 after pivot (x1 row): should not have x1 col boxed in row 2 highlight
    check("updated eq[0] no \\boxed in row1 when row2 highlighted",
          r"\boxed{" not in upd[0])

    # Coefficients in output should be human-readable (no long scientific notation)
    for eq in upd:
        check(f"no 'e+' scientific notation in '{eq[:40]}…'",
              "e+" not in eq and "e-" not in eq)
except Exception as e:
    check("LaTeX fraction format no exception", False, str(e))
    traceback.print_exc()


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "═"*55)
passed = sum(1 for _, ok in results if ok)
total  = len(results)
failed = [(lbl, ok) for lbl, ok in results if not ok]
print(f"  Result: {passed}/{total} passed")
if failed:
    print(f"\n  FAILED ({len(failed)}):")
    for lbl, _ in failed:
        print(f"    {FAIL}  {lbl}")
else:
    print("  All checks passed! 🎉")
print("═"*55)
sys.exit(0 if not failed else 1)
