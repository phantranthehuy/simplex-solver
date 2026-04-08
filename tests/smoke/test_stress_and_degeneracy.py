import random
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from backend.main import app  # noqa: E402


OPTIMAL_LABEL = "Nghi\u1ec7m t\u1ed1i \u01b0u"
UNBOUNDED_LABEL = "Kh\u00f4ng b\u1ecb ch\u1eb7n"


client = TestClient(app)


@pytest.mark.parametrize("seed", list(range(8)))
def test_randomized_box_lp_learning_and_production_objective_agree(seed):
    rng = random.Random(seed)
    n_vars = 3

    objective = [rng.randint(1, 6) for _ in range(n_vars)]

    constraints = []
    rhs = []
    types = []

    upper_bounds = []
    for j in range(n_vars):
        ub = rng.randint(3, 10)
        upper_bounds.append(ub)
        row = [0] * n_vars
        row[j] = 1
        constraints.append(row)
        rhs.append(ub)
        types.append("<=")

    for _ in range(2):
        row = [rng.randint(0, 4) for _ in range(n_vars)]
        if sum(row) == 0:
            row[rng.randrange(n_vars)] = 1
        cap = sum(row[j] * upper_bounds[j] for j in range(n_vars))
        constraints.append(row)
        rhs.append(max(1, int(0.7 * cap)))
        types.append("<=")

    payload = {
        "goal": "max",
        "objective": objective,
        "constraints": constraints,
        "types": types,
        "rhs": rhs,
    }

    r_learning = client.post("/api/v1/simplex/solve", json={"mode": "learning", **payload})
    r_production = client.post("/api/v1/simplex/solve", json={"mode": "production", **payload})

    assert r_learning.status_code == 200
    assert r_production.status_code == 200

    learning_data = r_learning.json()
    production_data = r_production.json()

    assert learning_data["steps"][-1]["step_name"] == OPTIMAL_LABEL
    assert production_data["result"]["status"] == "optimal"

    z_learning = float(learning_data["steps"][-1]["tableau"][0][-1])
    z_production = float(production_data["result"]["objective_value"])
    assert z_production == pytest.approx(z_learning, rel=1e-6, abs=1e-6)


@pytest.mark.parametrize(
    "payload",
    [
        {
            "mode": "learning",
            "goal": "max",
            "objective": [1, 0],
            "constraints": [[1, 1], [1, 0], [0, 1]],
            "types": ["<=", "<=", "<="],
            "rhs": [2, 2, 3],
        },
        {
            "mode": "learning",
            "goal": "max",
            "objective": [2, 2, 1],
            "constraints": [[1, 1, 0], [1, 0, 1], [0, 1, 1], [1, 1, 1]],
            "types": ["<=", "<=", "<=", "<="],
            "rhs": [2, 1, 1, 2],
        },
    ],
)
def test_harder_degeneracy_suite_terminates(payload):
    response = client.post("/api/v1/simplex/solve", json=payload)
    assert response.status_code == 200

    steps = response.json()["steps"]
    assert steps[-1]["step_name"] in {OPTIMAL_LABEL, UNBOUNDED_LABEL, "Vô nghiệm"}


def test_harder_degeneracy_suite_triggers_bland_tie_break():
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
    assert any("Bland tie-break" in (step.get("explanation") or "") for step in steps)
