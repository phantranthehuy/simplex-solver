"""
solver_wrapper.py
-----------------
Wrapper around simplex_engine for debugging and validation.
Provides a clean interface to the solver with logging and checkpoints.
"""

import numpy as np
from simplex_engine import standardize, solve_steps as _solve_steps
from debug_utils import logger, log_section, log_input, log_array, checkpoint
from validators import validate_form_inputs, validate_solver_output, validate_serialization

def solve_with_debug(objective, constraints, types, goal):
    """
    Wrapper around solve_steps with comprehensive logging.

    Parameters
    ----------
    objective : list[float]
        Objective coefficients
    constraints : list[list[float]]
        Each row = [a1, a2, ..., rhs]
    types : list[str]
        Constraint types (<=, >=, =)
    goal : str
        Optimization goal (min or max)

    Returns
    -------
    steps : list[dict]
        Solver steps with debug info attached
    """
    log_section("SOLVE WITH DEBUG")

    # Step 1: Validate inputs
    logger.debug("\n[STEP 1] Validating inputs...")
    n_vars = len(objective)
    m_constraints = len(constraints)

    is_valid, error = validate_form_inputs(n_vars, m_constraints, objective, constraints, types, goal)
    if not is_valid:
        logger.error(f"Input validation failed: {error}")
        raise ValueError(error)

    # Step 2: Run standardize to see what tableau looks like
    logger.debug("\n[STEP 2] Running standardize()...")
    try:
        init = standardize(objective, constraints, types, goal)
        checkpoint("After standardize()", {
            "basis": init["basis"],
            "var_names": init["var_names"],
            "has_phase1": init["has_phase1"],
            "n_art": init["n_art"],
        })

        logger.debug("\nInitial tableau:")
        log_array("tableau", init["tableau"])

    except Exception as e:
        logger.error(f"standardize() failed: {e}")
        raise

    # Step 3: Run solver
    logger.debug("\n[STEP 3] Running solve_steps()...")
    try:
        steps = _solve_steps(objective, constraints, types, goal)
        checkpoint("After solve_steps()", {
            "num_steps": len(steps),
            "final_status": steps[-1]["step_name"] if steps else "unknown",
        })
    except Exception as e:
        logger.error(f"solve_steps() failed: {e}")
        raise

    # Step 4: Validate output
    logger.debug("\n[STEP 4] Validating solver output...")
    is_valid, error = validate_solver_output(steps, init["var_names"], goal)
    if not is_valid:
        logger.error(f"Output validation failed: {error}")
        raise ValueError(error)

    # Step 5: Show final state
    logger.debug("\n[STEP 5] Final state:")
    final_step = steps[-1]
    logger.debug(f"  Status: {final_step['step_name']}")
    logger.debug(f"  Basis: {final_step['basis']}")
    if final_step["basis"]:
        final_tableau = final_step["tableau"]
        logger.debug(f"  Solution values:")
        for i, var in enumerate(final_step["basis"]):
            val = final_tableau[i + 1, -1] if i + 1 < final_tableau.shape[0] else "N/A"
            logger.debug(f"    {var} = {val}")

    logger.debug("\n✓ solve_with_debug completed successfully")
    return steps

def validate_and_serialize(steps, var_names, goal, objective, obj_constant=0):
    """
    Validate steps and prepare for serialization to JSON.

    Returns
    -------
    dict
        Serialized data ready for dcc.Store
    """
    log_section("VALIDATE AND SERIALIZE")

    logger.debug("\n[STEP 1] Validating solver output...")
    is_valid, error = validate_solver_output(steps, var_names, goal)
    if not is_valid:
        logger.error(f"Validation failed: {error}")
        raise ValueError(error)

    # Step 2: Convert numpy arrays to lists
    logger.debug("\n[STEP 2] Converting numpy arrays to JSON-serializable format...")
    serialized = []
    for i, s in enumerate(steps):
        sd = {
            "step_name": s["step_name"],
            "tableau": s["tableau"].tolist(),  # Convert numpy to list
            "basis": s["basis"],
            "pivot_row": s["pivot_row"],
            "pivot_col": s["pivot_col"],
            "ratios": s["ratios"],
            "explanation": s["explanation"],
            "var_names": s.get("var_names"),
            "phase": s.get("phase", 2),
        }
        if "phase1_tab" in s and s["phase1_tab"] is not None:
            sd["phase1_tab"] = s["phase1_tab"].tolist()
        if "art_vars" in s:
            sd["art_vars"] = s["art_vars"]
        serialized.append(sd)

    result = {
        "steps": serialized,
        "var_names": var_names,
        "goal": goal,
        "objective": objective,
        "obj_constant": float(obj_constant) if obj_constant is not None else 0.0,
        "error": None,
    }

    # Step 3: Validate serialization
    logger.debug("\n[STEP 3] Validating serialization...")
    is_valid, error = validate_serialization(result)
    if not is_valid:
        logger.error(f"Serialization validation failed: {error}")
        raise ValueError(error)

    checkpoint("Serialized data", {
        "num_steps": len(serialized),
        "var_names_count": len(var_names),
        "goal": goal,
    })

    logger.debug("\n✓ Serialization completed successfully")
    return result
