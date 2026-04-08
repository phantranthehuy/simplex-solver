#!/usr/bin/env python3
"""Benchmark learning vs production simplex modes via in-process FastAPI calls."""

from __future__ import annotations

import argparse
import random
import statistics
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.main import app  # noqa: E402


def generate_bounded_lp(n_vars: int, extra_constraints: int, rng: random.Random):
    """Generate a feasible and bounded LP in max form.

    Construction:
    - Nonnegative variables.
    - n upper-bound constraints x_j <= u_j.
    - extra dense resource constraints with positive coefficients.
    This guarantees boundedness while keeping matrix structure non-trivial.
    """
    objective = [round(rng.uniform(1.0, 30.0), 4) for _ in range(n_vars)]

    constraints = []
    types = []
    rhs = []

    # Individual upper bounds keep the model bounded.
    ub_values = [round(rng.uniform(5.0, 30.0), 4) for _ in range(n_vars)]
    for j in range(n_vars):
        row = [0.0] * n_vars
        row[j] = 1.0
        constraints.append(row)
        types.append("<=")
        rhs.append(ub_values[j])

    # Extra dense constraints add realistic coupling.
    for _ in range(extra_constraints):
        row = [round(rng.uniform(0.2, 3.0), 4) for _ in range(n_vars)]
        # Build a RHS that is feasible for x=0 and not overly tight.
        rhs_val = sum(row[j] * ub_values[j] for j in range(n_vars)) * rng.uniform(0.45, 0.8)
        constraints.append(row)
        types.append("<=")
        rhs.append(round(rhs_val, 4))

    return {
        "goal": "max",
        "objective": objective,
        "constraints": constraints,
        "types": types,
        "rhs": rhs,
        "variable_signs": ["nonnegative"] * n_vars,
    }


def run_single_case(client: TestClient, payload_base: dict, mode: str) -> float:
    payload = {**payload_base, "mode": mode}
    t0 = time.perf_counter()
    response = client.post("/api/v1/simplex/solve", json=payload)
    elapsed = time.perf_counter() - t0

    if response.status_code != 200:
        raise RuntimeError(f"{mode} returned HTTP {response.status_code}: {response.text[:300]}")

    data = response.json()
    if data.get("status") not in {"success", "not_implemented"}:
        raise RuntimeError(f"{mode} returned unexpected status: {data}")

    if mode == "learning":
        steps = data.get("steps")
        if not isinstance(steps, list) or not steps:
            raise RuntimeError("learning response does not contain non-empty steps")
    else:
        result = data.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("production response missing result object")

    return elapsed


def benchmark(
    n_vars: int,
    extra_constraints: int,
    cases: int,
    seed: int,
):
    rng = random.Random(seed)
    client = TestClient(app)

    learning_times = []
    production_times = []

    for _ in range(cases):
        payload_base = generate_bounded_lp(n_vars=n_vars, extra_constraints=extra_constraints, rng=rng)

        learning_times.append(run_single_case(client, payload_base, "learning"))
        production_times.append(run_single_case(client, payload_base, "production"))

    learning_avg = statistics.mean(learning_times)
    learning_med = statistics.median(learning_times)
    production_avg = statistics.mean(production_times)
    production_med = statistics.median(production_times)

    speedup_avg = (learning_avg / production_avg) if production_avg > 0 else float("inf")
    speedup_med = (learning_med / production_med) if production_med > 0 else float("inf")

    print("Simplex Mode Benchmark")
    print(f"- n_vars: {n_vars}")
    print(f"- extra_constraints: {extra_constraints}")
    print(f"- cases: {cases}")
    print(f"- seed: {seed}")
    print()
    print("Timing summary (seconds):")
    print(f"- learning  avg: {learning_avg:.6f} | median: {learning_med:.6f}")
    print(f"- production avg: {production_avg:.6f} | median: {production_med:.6f}")
    print()
    print("Speedup (learning / production):")
    print(f"- avg speedup: {speedup_avg:.3f}x")
    print(f"- median speedup: {speedup_med:.3f}x")


def parse_args():
    parser = argparse.ArgumentParser(description="Benchmark simplex learning vs production modes")
    parser.add_argument("--n-vars", type=int, default=24, help="Number of decision variables")
    parser.add_argument(
        "--extra-constraints",
        type=int,
        default=28,
        help="Additional dense constraints on top of per-variable upper bounds",
    )
    parser.add_argument("--cases", type=int, default=6, help="Number of random LP cases")
    parser.add_argument("--seed", type=int, default=20260406, help="Random seed")
    return parser.parse_args()


def main():
    args = parse_args()
    benchmark(
        n_vars=max(2, args.n_vars),
        extra_constraints=max(1, args.extra_constraints),
        cases=max(1, args.cases),
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
