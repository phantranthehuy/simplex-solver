import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "frontend"))

from backend.main import app  # noqa: E402
import callbacks as ui_callbacks  # noqa: E402


client = TestClient(app)


def _collect_text(node):
    if node is None:
        return []
    if isinstance(node, (list, tuple)):
        chunks = []
        for child in node:
            chunks.extend(_collect_text(child))
        return chunks
    if isinstance(node, str):
        return [node]
    if isinstance(node, (int, float)):
        return [str(node)]

    chunks = []
    expression = getattr(node, "expression", None)
    if isinstance(expression, str):
        chunks.append(expression)

    children = getattr(node, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            chunks.extend(_collect_text(child))
    elif children is not None:
        chunks.extend(_collect_text(children))

    return chunks


def test_unbounded_render_parity_across_display_modes():
    payload = {
        "mode": "learning",
        "goal": "min",
        "objective": [-2, 4, 0, 0],
        "constraints": [[-1, 1, 1, 0], [-1, 0, 0, 1]],
        "types": ["=", "="],
        "rhs": [2, 1],
    }

    response = client.post("/api/v1/simplex/solve", json=payload)
    assert response.status_code == 200

    data = response.json()
    steps = ui_callbacks._deserialize_steps(data["steps"])
    var_names = data.get("var_names", [])

    table_blocks = ui_callbacks.render_table_mode(steps, var_names, obj_constant=0.0, goal="min")
    classic_blocks = ui_callbacks.render_algebra_mode_classic(
        steps,
        var_names,
        goal="min",
        objective=payload["objective"],
        obj_constant=0.0,
    )
    algebra_blocks = ui_callbacks.render_algebra_mode(
        steps,
        var_names,
        goal="min",
        objective=payload["objective"],
        obj_constant=0.0,
    )

    assert len(table_blocks) > 0
    assert len(classic_blocks) > 0
    assert len(algebra_blocks) > 0

    table_text = str(table_blocks).lower()
    classic_text = str(classic_blocks).lower()
    algebra_text = str(algebra_blocks).lower()

    assert "không có hàng pivot hợp lệ" in table_text
    assert "không có hàng pivot hợp lệ" in classic_text
    assert "không có hàng pivot hợp lệ" in algebra_text

    # Full algebra keeps one additional reasoning step that table mode does not include.
    assert "tia khả thi" in algebra_text


def test_render_modes_cover_terminal_statuses_and_depth_gaps():
    matrix = [
        (
            {
                "mode": "learning",
                "goal": "max",
                "objective": [3, 2],
                "constraints": [[2, 1], [1, 1]],
                "types": ["<=", "<="],
                "rhs": [100, 80],
            },
            "tối ưu",
        ),
        (
            {
                "mode": "learning",
                "goal": "min",
                "objective": [-2, 4, 0, 0],
                "constraints": [[-1, 1, 1, 0], [-1, 0, 0, 1]],
                "types": ["=", "="],
                "rhs": [2, 1],
            },
            "không bị chặn",
        ),
        (
            {
                "mode": "learning",
                "goal": "max",
                "objective": [1, 1],
                "constraints": [[1, 1], [1, 0], [0, 1]],
                "types": ["<=", ">=", ">="],
                "rhs": [1, 1, 1],
            },
            "vô nghiệm",
        ),
    ]

    for payload, marker in matrix:
        response = client.post("/api/v1/simplex/solve", json=payload)
        assert response.status_code == 200

        data = response.json()
        steps = ui_callbacks._deserialize_steps(data["steps"])
        var_names = data.get("var_names", [])

        table_blocks = ui_callbacks.render_table_mode(steps, var_names, obj_constant=0.0, goal=payload["goal"])
        classic_blocks = ui_callbacks.render_algebra_mode_classic(
            steps,
            var_names,
            goal=payload["goal"],
            objective=payload["objective"],
            obj_constant=0.0,
        )
        algebra_blocks = ui_callbacks.render_algebra_mode(
            steps,
            var_names,
            goal=payload["goal"],
            objective=payload["objective"],
            obj_constant=0.0,
        )

        table_text = str(table_blocks).lower()
        classic_text = str(classic_blocks).lower()
        algebra_text = str(algebra_blocks).lower()

        assert marker in table_text
        assert marker in classic_text
        assert marker in algebra_text
        assert table_text != algebra_text


def test_render_modes_keep_min_objective_sign_consistent():
    payload = {
        "mode": "learning",
        "goal": "min",
        "objective": [-4, -2, 0, 0],
        "constraints": [[-1, 1, 1, 0], [1, 0, 0, 1]],
        "types": ["=", "="],
        "rhs": [2, 1],
    }

    response = client.post("/api/v1/simplex/solve", json=payload)
    assert response.status_code == 200

    data = response.json()
    steps = ui_callbacks._deserialize_steps(data["steps"])
    var_names = data.get("var_names", [])

    table_blocks = ui_callbacks.render_table_mode(steps, var_names, obj_constant=-5.0, goal="min")
    algebra_blocks = ui_callbacks.render_algebra_mode(
        steps,
        var_names,
        goal="min",
        objective=payload["objective"],
        obj_constant=-5.0,
    )

    text_table = str(table_blocks)
    text_algebra = str(algebra_blocks)

    assert "-15" in text_table
    assert "-15" in text_algebra


def test_render_result_shows_normalization_notices_consistently():
    payload = {
        "mode": "learning",
        "goal": "max",
        "objective": [1],
        "constraints": [[-1], [1]],
        "types": ["<=", "<="],
        "rhs": [-1, 3],
        "variable_signs": ["free"],
    }

    response = client.post("/api/v1/simplex/solve", json=payload)
    assert response.status_code == 200
    data = response.json()

    store_data = {
        "error": None,
        "steps": data["steps"],
        "var_names": data.get("var_names", []),
        "goal": payload["goal"],
        "objective": payload["objective"],
        "obj_constant": 5.0,
        "mode": "learning",
        "backend_message": data.get("message"),
        "normalization": data.get("normalization", {}),
        "normalized_model": data.get("normalized_model", {}),
        "input_echo": {
            "goal": payload["goal"],
            "objective": payload["objective"],
            "constraints": payload["constraints"],
            "types": payload["types"],
            "rhs": payload["rhs"],
        },
    }

    rendered = ui_callbacks.render_result(store_data, display_mode="both", algebra_visible=True)
    rendered_text = " ".join(_collect_text(rendered))

    assert "Chuẩn hóa RHS" in rendered_text
    assert "Tách biến tự do" in rendered_text
    assert "Hiệu chỉnh hằng số mục tiêu" in rendered_text


def test_render_result_hides_normalized_model_when_no_stage1_change():
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

    store_data = {
        "error": None,
        "steps": data["steps"],
        "var_names": data.get("var_names", []),
        "goal": payload["goal"],
        "objective": payload["objective"],
        "obj_constant": 0.0,
        "mode": "learning",
        "backend_message": data.get("message"),
        "normalization": data.get("normalization", {}),
        "normalized_model": data.get("normalized_model", {}),
        "input_echo": {
            "goal": payload["goal"],
            "objective": payload["objective"],
            "constraints": payload["constraints"],
            "types": payload["types"],
            "rhs": payload["rhs"],
        },
    }

    rendered = ui_callbacks.render_result(store_data, display_mode="both", algebra_visible=True)
    rendered_text = " ".join(_collect_text(rendered))

    assert "Mô hình đã chuẩn hóa:" not in rendered_text


def test_render_result_toggle_can_force_hide_normalized_model_notice():
    payload = {
        "mode": "learning",
        "goal": "max",
        "objective": [1],
        "constraints": [[-1], [1]],
        "types": ["<=", "<="],
        "rhs": [-1, 3],
        "variable_signs": ["free"],
    }

    response = client.post("/api/v1/simplex/solve", json=payload)
    assert response.status_code == 200
    data = response.json()

    store_data = {
        "error": None,
        "steps": data["steps"],
        "var_names": data.get("var_names", []),
        "goal": payload["goal"],
        "objective": payload["objective"],
        "obj_constant": 0.0,
        "mode": "learning",
        "backend_message": data.get("message"),
        "normalization": data.get("normalization", {}),
        "normalized_model": data.get("normalized_model", {}),
        "input_echo": {
            "goal": payload["goal"],
            "objective": payload["objective"],
            "constraints": payload["constraints"],
            "types": payload["types"],
            "rhs": payload["rhs"],
        },
    }

    rendered = ui_callbacks.render_result(
        store_data,
        display_mode="both",
        algebra_visible=True,
        show_normalized_model=False,
    )
    rendered_text = " ".join(_collect_text(rendered))

    assert "Mô hình đã chuẩn hóa:" not in rendered_text


def test_phase1_transition_does_not_show_empty_artificial_var_parentheses():
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
    data = response.json()

    steps = ui_callbacks._deserialize_steps(data["steps"])
    var_names = data.get("var_names", [])
    blocks = ui_callbacks.render_algebra_mode(
        steps,
        var_names,
        goal=payload["goal"],
        objective=payload["objective"],
        obj_constant=0.0,
    )

    rendered_text = " ".join(_collect_text(blocks))
    assert "Loại bỏ các biến thêm vào ( )" not in rendered_text
    assert ("a_{" in rendered_text) or ("biến nhân tạo" in rendered_text)
