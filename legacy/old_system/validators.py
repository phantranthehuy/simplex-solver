"""
validators.py
--------------
Input validation and data integrity checks.
"""

from debug_utils import logger, validate_input, checkpoint

def validate_form_inputs(n_vars, m_constraints, objective, constraints, types, goal):
    """
    Validate all form inputs before passing to solver.
    Returns (is_valid, error_message).
    """
    log_section = lambda x: logger.debug(f"\n--- {x} ---")

    log_section("VALIDATING FORM INPUTS")

    # Validate dimensions
    if not (1 <= n_vars <= 10):
        return False, f"n_vars must be 1-10, got {n_vars}"
    if not (1 <= m_constraints <= 10):
        return False, f"m_constraints must be 1-10, got {m_constraints}"

    logger.debug(f"  n_vars={n_vars}, m_constraints={m_constraints}")

    # Validate objective
    if not isinstance(objective, list) or len(objective) != n_vars:
        return False, f"objective must be list of {n_vars} floats"

    try:
        obj_floats = [float(v) for v in objective]
        logger.debug(f"  objective: {obj_floats}")
    except (ValueError, TypeError) as e:
        return False, f"objective contains non-numeric values: {e}"

    # Validate constraints
    if not isinstance(constraints, list) or len(constraints) != m_constraints:
        return False, f"constraints must be list of {m_constraints} rows"

    try:
        for i, con in enumerate(constraints):
            if not isinstance(con, list) or len(con) != n_vars + 1:
                return False, f"constraint {i}: expected {n_vars+1} values, got {len(con)}"
            con_floats = [float(v) for v in con]
            coeffs = con_floats[:n_vars]
            rhs = con_floats[n_vars]
            logger.debug(f"  constraint {i}: {coeffs} (RHS={rhs})")
    except (ValueError, TypeError) as e:
        return False, f"constraint contains non-numeric values: {e}"

    # Validate types
    if not isinstance(types, list) or len(types) != m_constraints:
        return False, f"types must be list of {m_constraints} operators"

    allowed_ops = {"<=", ">=", "="}
    for i, op in enumerate(types):
        if op not in allowed_ops:
            return False, f"constraint {i}: invalid operator '{op}'. Must be <=, >=, or ="
    logger.debug(f"  types: {types}")

    # Validate goal
    if goal not in {"min", "max"}:
        return False, f"goal must be 'min' or 'max', got '{goal}'"
    logger.debug(f"  goal: {goal}")

    logger.debug("\n✓ All form inputs valid")
    return True, None

def validate_solver_output(steps, var_names, goal):
    """
    Validate solver output structure.
    Returns (is_valid, error_message).
    """
    log_section = lambda x: logger.debug(f"\n--- {x} ---")

    log_section("VALIDATING SOLVER OUTPUT")

    if not isinstance(steps, list):
        return False, f"steps must be list, got {type(steps)}"

    logger.debug(f"  Number of steps: {len(steps)}")

    if len(steps) == 0:
        return False, "steps is empty"

    # Check structure of first step
    first_step = steps[0]
    required_keys = {"step_name", "tableau", "basis", "var_names"}
    missing_keys = required_keys - set(first_step.keys())
    if missing_keys:
        return False, f"step missing keys: {missing_keys}"

    logger.debug(f"  First step name: {first_step['step_name']}")
    logger.debug(f"  First step basis: {first_step['basis']}")
    logger.debug(f"  Tableau shape: {first_step['tableau'].shape}")

    # Check var_names consistency
    if not isinstance(var_names, list):
        return False, f"var_names must be list, got {type(var_names)}"

    logger.debug(f"  var_names: {var_names}")
    logger.debug(f"  goal: {goal}")

    logger.debug("\n✓ Solver output structure valid")
    return True, None

def validate_serialization(serialized_data):
    """
    Validate serialized steps data before sending to frontend.
    Returns (is_valid, error_message).
    """
    log_section = lambda x: logger.debug(f"\n--- {x} ---")

    log_section("VALIDATING SERIALIZATION")

    if not isinstance(serialized_data, dict):
        return False, f"expected dict, got {type(serialized_data)}"

    required_keys = {"steps", "var_names", "goal", "objective"}
    missing_keys = required_keys - set(serialized_data.keys())
    if missing_keys:
        return False, f"missing keys: {missing_keys}"

    steps_list = serialized_data.get("steps", [])
    if not isinstance(steps_list, list):
        return False, f"steps must be list, got {type(steps_list)}"

    logger.debug(f"  Number of steps: {len(steps_list)}")
    logger.debug(f"  var_names: {serialized_data['var_names']}")
    logger.debug(f"  goal: {serialized_data['goal']}")
    logger.debug(f"  objective: {serialized_data['objective']}")

    # Check tableau is JSON-serializable (should be lists, not numpy arrays)
    for i, step in enumerate(steps_list):
        if not isinstance(step.get("tableau"), list):
            return False, f"step[{i}]: tableau should be list after serialization, got {type(step.get('tableau'))}"

    logger.debug("\n✓ Serialization valid")
    return True, None
