import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from backend.main import app  # noqa: E402
from backend.api import simplex_router  # noqa: E402


OPTIMAL_LABEL = "Nghi\u1ec7m t\u1ed1i \u01b0u"
UNBOUNDED_LABEL = "Kh\u00f4ng b\u1ecb ch\u1eb7n"


client = TestClient(app)


def _extract_variable_values(final_step):
    tableau = final_step["tableau"]
    basis = final_step["basis"]
    values = {}
    for i, var_name in enumerate(basis, start=1):
        if i < len(tableau):
            values[var_name] = float(tableau[i][-1])
    return values


def test_learning_response_schema_is_json_safe():
    payload = {
        "mode": "learning",
        "goal": "max",
        "objective": [3, 2],
        "constraints": [[2, 1], [1, 1]],
        "types": ["<=", "<="],
        "rhs": [100, 80],
    }

    response = client.post("/api/v1/simplex/solve", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert data["mode"] == "learning"
    assert isinstance(data.get("steps"), list)
    assert len(data["steps"]) > 0

    step = data["steps"][0]
    required_keys = {
        "step_name",
        "tableau",
        "basis",
        "pivot_row",
        "pivot_col",
        "ratios",
        "explanation",
        "phase",
        "var_names",
    }
    assert required_keys.issubset(step.keys())
    assert isinstance(step["tableau"], list)


def test_learning_known_min_cases_regression():
    payload_unbounded = {
        "mode": "learning",
        "goal": "min",
        "objective": [-2, 4, 0, 0],
        "constraints": [[-1, 1, 1, 0], [-1, 0, 0, 1]],
        "types": ["=", "="],
        "rhs": [2, 1],
    }

    payload_optimal = {
        "mode": "learning",
        "goal": "min",
        "objective": [-4, -2, 0, 0],
        "constraints": [[-1, 1, 1, 0], [1, 0, 0, 1]],
        "types": ["=", "="],
        "rhs": [2, 1],
    }

    r1 = client.post("/api/v1/simplex/solve", json=payload_unbounded)
    r2 = client.post("/api/v1/simplex/solve", json=payload_optimal)

    assert r1.status_code == 200
    assert r2.status_code == 200

    final_1 = r1.json()["steps"][-1]
    final_2 = r2.json()["steps"][-1]

    assert final_1["step_name"] == UNBOUNDED_LABEL
    assert final_2["step_name"] == OPTIMAL_LABEL

    values = _extract_variable_values(final_2)
    x1 = values.get("x1", 0.0)
    x2 = values.get("x2", 0.0)
    x3 = values.get("x3", 0.0)
    x4 = values.get("x4", 0.0)

    assert x1 == pytest.approx(1.0)
    assert x2 == pytest.approx(3.0)
    assert x3 == pytest.approx(0.0)
    assert x4 == pytest.approx(0.0)

    # For this MIN case: Z = -raw - 5
    raw_z = float(final_2["tableau"][0][-1])
    original_z = -raw_z - 5
    assert original_z == pytest.approx(-15.0)


def test_stage1_rhs_sign_normalization_equivalence():
    # Problem A has a negative RHS and requires sign flipping in Stage 1.
    payload_negative_rhs = {
        "mode": "learning",
        "goal": "max",
        "objective": [1],
        "constraints": [[-1], [1]],
        "types": ["<=", "<="],
        "rhs": [-1, 3],
    }

    # Problem B is already normalized and should be equivalent.
    payload_normalized = {
        "mode": "learning",
        "goal": "max",
        "objective": [1],
        "constraints": [[1], [1]],
        "types": [">=", "<="],
        "rhs": [1, 3],
    }

    r_neg = client.post("/api/v1/simplex/solve", json=payload_negative_rhs)
    r_norm = client.post("/api/v1/simplex/solve", json=payload_normalized)

    assert r_neg.status_code == 200
    assert r_norm.status_code == 200

    final_neg = r_neg.json()["steps"][-1]
    final_norm = r_norm.json()["steps"][-1]

    assert final_neg["step_name"] == OPTIMAL_LABEL
    assert final_norm["step_name"] == OPTIMAL_LABEL

    values_neg = _extract_variable_values(final_neg)
    values_norm = _extract_variable_values(final_norm)

    assert values_neg.get("x1", 0.0) == pytest.approx(3.0)
    assert values_norm.get("x1", 0.0) == pytest.approx(3.0)

    z_neg = float(final_neg["tableau"][0][-1])
    z_norm = float(final_norm["tableau"][0][-1])
    assert z_neg == pytest.approx(3.0)
    assert z_norm == pytest.approx(3.0)

    norm_meta = r_neg.json().get("normalization", {})
    assert isinstance(norm_meta.get("rhs_flips"), list)
    assert len(norm_meta["rhs_flips"]) >= 1


def test_stage1_presolve_redundancy_and_scaling_metadata():
    payload = {
        "mode": "learning",
        "goal": "max",
        "objective": [1],
        "constraints": [[2], [2], [2]],
        "types": ["<=", "<=", "<="],
        "rhs": [10, 6, 12],
    }

    response = client.post("/api/v1/simplex/solve", json=payload)
    assert response.status_code == 200

    data = response.json()
    norm = data.get("normalization", {})
    presolve = norm.get("presolve", {})

    removed = presolve.get("removed_constraints", [])
    kept = presolve.get("kept_constraints", [])
    scaling = presolve.get("scaling", [])

    assert any(item.get("row") == 1 for item in removed)
    assert any(item.get("row") == 3 for item in removed)
    assert kept == [2]
    assert len(scaling) == 3


def test_stage1_presolve_detects_contradiction_early():
    payload = {
        "mode": "production",
        "goal": "max",
        "objective": [1],
        "constraints": [[1], [1]],
        "types": ["<=", ">="],
        "rhs": [1, 3],
    }

    response = client.post("/api/v1/simplex/solve", json=payload)
    assert response.status_code == 400
    assert "Presolve phát hiện mâu thuẫn" in response.json().get("detail", "")


def test_stage1_unrestricted_decomposition_in_production():
    # max x1  s.t.  x1 <= 2,  -x1 <= 1  with x1 free
    # Equivalent bounds: -1 <= x1 <= 2 => optimum x1*=2, Z*=2
    payload = {
        "mode": "production",
        "goal": "max",
        "objective": [1],
        "constraints": [[1], [-1]],
        "types": ["<=", "<="],
        "rhs": [2, 1],
        "variable_signs": ["free"],
    }

    response = client.post("/api/v1/simplex/solve", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert data["mode"] == "production"

    norm = data.get("normalization", {})
    substitutions = norm.get("unrestricted_substitutions", [])
    assert len(substitutions) == 1
    assert substitutions[0]["original"] == "x1"

    result = data["result"]
    assert result["status"] == "optimal"

    solution = result["solution_map"]
    x_plus = solution.get("x1_plus", 0.0)
    x_minus = solution.get("x1_minus", 0.0)
    assert x_plus - x_minus == pytest.approx(2.0)
    assert result["objective_value"] == pytest.approx(2.0)


def test_stage1_unrestricted_decomposition_in_learning_schema():
    payload = {
        "mode": "learning",
        "goal": "max",
        "objective": [1],
        "constraints": [[1], [-1]],
        "types": ["<=", "<="],
        "rhs": [2, 1],
        "variable_signs": ["free"],
    }

    response = client.post("/api/v1/simplex/solve", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert data["mode"] == "learning"
    assert isinstance(data.get("steps"), list) and len(data["steps"]) > 0

    var_names = data.get("var_names", [])
    assert "x1_plus" in var_names
    assert "x1_minus" in var_names

    norm = data.get("normalization", {})
    substitutions = norm.get("unrestricted_substitutions", [])
    assert len(substitutions) == 1
    assert substitutions[0]["formula"].startswith("x1 = x1_plus - x1_minus")


def test_stage2_phase1_is_triggered_for_ge_or_equal_constraints():
    payload = {
        "mode": "learning",
        "goal": "max",
        "objective": [3, 2],
        "constraints": [[1, 1], [1, 0]],
        "types": [">=", "="],
        "rhs": [4, 2],
    }

    response = client.post("/api/v1/simplex/solve", json=payload)
    assert response.status_code == 200

    steps = response.json()["steps"]
    assert len(steps) > 0

    # At least one step must be tagged as Phase 1.
    assert any(step.get("phase") == 1 for step in steps)


def test_learning_infeasible_case_regression():
    payload = {
        "mode": "learning",
        "goal": "max",
        "objective": [1, 1],
        "constraints": [[1, 1], [1, 0], [0, 1]],
        "types": ["<=", ">=", ">="],
        "rhs": [1, 1, 1],
    }

    response = client.post("/api/v1/simplex/solve", json=payload)
    assert response.status_code == 200

    final = response.json()["steps"][-1]
    assert final["step_name"] == "Vô nghiệm"


def test_stage4_bland_tie_break_regression():
    payload = {
        "mode": "learning",
        "goal": "max",
        "objective": [1, 0],
        "constraints": [[1, 1], [1, 0], [0, 1]],
        "types": ["<=", "<=", "<="],
        "rhs": [2, 2, 3],
    }

    response = client.post("/api/v1/simplex/solve", json=payload)
    assert response.status_code == 200

    steps = response.json()["steps"]
    assert any("Bland tie-break" in (s.get("explanation") or "") for s in steps)
    assert steps[-1]["step_name"] in {OPTIMAL_LABEL, UNBOUNDED_LABEL, "Vô nghiệm"}


def test_production_mode_minimal_contract_does_not_break():
    payload = {
        "mode": "production",
        "goal": "max",
        "objective": [3, 2],
        "constraints": [[2, 1], [1, 1]],
        "types": ["<=", "<="],
        "rhs": [100, 80],
    }

    response = client.post("/api/v1/simplex/solve", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data.get("status") == "success"
    assert data.get("mode") == "production"
    assert "result" in data
    assert isinstance(data["result"], dict)

    result = data["result"]
    required = {
        "status",
        "solution_map",
        "objective_value",
        "iterations",
        "termination_reason",
        "engine",
        "sensitivity",
    }
    assert required.issubset(result.keys())
    assert result["status"] == "optimal"
    assert result["engine"] in {"revised_simplex", "full_tableau_fallback"}

    x1 = result["solution_map"].get("x1", 0.0)
    x2 = result["solution_map"].get("x2", 0.0)
    assert x1 == pytest.approx(20.0)
    assert x2 == pytest.approx(60.0)
    assert result["objective_value"] == pytest.approx(180.0)


def test_production_mode_handles_phase1_constraints():
    payload = {
        "mode": "production",
        "goal": "max",
        "objective": [1, 1],
        "constraints": [[1, 1], [1, 0], [0, 1]],
        "types": [">=", "<=", "<="],
        "rhs": [4, 2, 3],
    }

    response = client.post("/api/v1/simplex/solve", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert data["mode"] == "production"

    result = data["result"]
    assert result["status"] == "optimal"
    assert result["objective_value"] == pytest.approx(5.0)
    assert result["solution_map"].get("x1", 0.0) == pytest.approx(2.0)
    assert result["solution_map"].get("x2", 0.0) == pytest.approx(3.0)


def test_production_revised_simplex_scaled_coefficients_stability():
    payload = {
        "mode": "production",
        "goal": "max",
        "objective": [1, 1],
        "constraints": [[1_000_000, 2_000_000], [1, 0], [0, 1]],
        "types": ["<=", "<=", "<="],
        "rhs": [4_000_000, 2, 3],
    }

    response = client.post("/api/v1/simplex/solve", json=payload)
    assert response.status_code == 200

    data = response.json()
    result = data["result"]
    assert result["status"] == "optimal"
    assert result["engine"] in {"revised_simplex", "full_tableau_fallback"}
    assert "sensitivity" in result
    assert result["objective_value"] == pytest.approx(3.0)
    assert result["solution_map"].get("x1", 0.0) == pytest.approx(2.0)
    assert result["solution_map"].get("x2", 0.0) == pytest.approx(1.0)


def test_production_infeasible_case_regression():
    payload = {
        "mode": "production",
        "goal": "max",
        "objective": [1, 1],
        "constraints": [[1, 1], [1, 0], [0, 1]],
        "types": ["<=", ">=", ">="],
        "rhs": [1, 1, 1],
    }

    response = client.post("/api/v1/simplex/solve", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert data["mode"] == "production"
    assert data["result"]["status"] == "infeasible"


def test_runtime_guardrail_dimension_cap_for_learning_mode():
    payload = {
        "mode": "learning",
        "goal": "max",
        "objective": [1.0] * 25,
        "constraints": [[1.0] * 25],
        "types": ["<="],
        "rhs": [10.0],
    }

    response = client.post("/api/v1/simplex/solve", json=payload)
    assert response.status_code == 413
    assert "vượt giới hạn" in response.json().get("detail", "")


def test_runtime_guardrail_soft_timeout_for_learning_mode(monkeypatch):
    def _slow_solver(_):
        time.sleep(0.05)
        return []

    monkeypatch.setitem(simplex_router.SOFT_TIMEOUT_SECONDS, "learning", 0.001)
    monkeypatch.setattr(simplex_router, "run_full_tableau_with_snapshots", _slow_solver)

    payload = {
        "mode": "learning",
        "goal": "max",
        "objective": [1.0],
        "constraints": [[1.0]],
        "types": ["<="],
        "rhs": [1.0],
    }

    response = client.post("/api/v1/simplex/solve", json=payload)
    assert response.status_code == 503
    assert "quá tải thời gian xử lý" in response.json().get("detail", "")


def test_max_case_with_lower_bounds_regression():
    # User-reported case:
    # max Z = 16x1 + 30x2 + 50x3
    # x1>=20; x2>=120; x3>=60
    # 3x1+3.5x2+5x3<=1440
    # 4x1+5x2+8x3<=1920
    # x1+1.5x2+3x3<=576
    payload = {
        "mode": "learning",
        "goal": "max",
        "objective": [16, 30, 50],
        "constraints": [
            [1, 0, 0],
            [0, 1, 0],
            [0, 0, 1],
            [3, 3.5, 5],
            [4, 5, 8],
            [1, 1.5, 3],
        ],
        "types": [">=", ">=", ">=", "<=", "<=", "<="],
        "rhs": [20, 120, 60, 1440, 1920, 576],
    }

    response = client.post("/api/v1/simplex/solve", json=payload)
    assert response.status_code == 200

    final = response.json()["steps"][-1]
    assert final["step_name"] == OPTIMAL_LABEL

    values = _extract_variable_values(final)
    x1 = values.get("x1", 0.0)
    x2 = values.get("x2", 0.0)
    x3 = values.get("x3", 0.0)

    assert x1 == pytest.approx(20.0)
    assert x2 == pytest.approx(250.66666666666666)
    assert x3 == pytest.approx(60.0)

    z = float(final["tableau"][0][-1])
    assert z == pytest.approx(10840.0)

    # The often-reported point (20, 260.666..., 60) is infeasible because:
    # x1 + 1.5*x2 + 3*x3 = 591 > 576
    lhs3 = 20.0 + 1.5 * 260.6666666667 + 3.0 * 60.0
    assert lhs3 > 576.0
