import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from typing import List, Optional, Any

try:
    from ..algorithms.stage1_parser import parse_and_validate
    from ..algorithms.stage2_standardizer import build_standard_form
    from ..algorithms.stage3_full_tableau import run_full_tableau_with_snapshots
    from ..algorithms.stage5_revised_simplex import run_revised_simplex
except ImportError:
    from algorithms.stage1_parser import parse_and_validate
    from algorithms.stage2_standardizer import build_standard_form
    from algorithms.stage3_full_tableau import run_full_tableau_with_snapshots
    from algorithms.stage5_revised_simplex import run_revised_simplex

# Cấu trúc Pydantic Schema kế thừa quy tắc Validation cốt lõi
class SimplexRequest(BaseModel):
    mode: str  # "learning" hoặc "production"
    goal: str  # "max" hoặc "min"
    objective: List[float]
    constraints: List[List[float]]
    types: List[str]
    rhs: List[float]
    variable_signs: Optional[List[str]] = None
    
    @field_validator('mode')
    @classmethod
    def validate_mode(cls, v):
        if v not in ["learning", "production"]:
            raise ValueError("Mode chỉ được phép là 'learning' hoặc 'production'")
        return v
        
    @field_validator('goal')
    @classmethod
    def validate_goal(cls, v):
        if v.lower() not in ["max", "min"]:
            raise ValueError("Goal chỉ được phép là 'max' hoặc 'min'")
        return v.lower()
        
    @field_validator('types')
    @classmethod
    def validate_types(cls, v):
        allowed_types = {"<=", ">=", "="}
        for t in v:
            if t not in allowed_types:
                raise ValueError(f"Loại ràng buộc không hợp lệ: {t}. Chỉ cho phép <=, >=, =")
        return v

    @field_validator('variable_signs')
    @classmethod
    def validate_variable_signs(cls, v):
        if v is None:
            return v

        nonneg_aliases = {"nonnegative", "non-negative", ">=0", "positive", "plus", "nn"}
        free_aliases = {"free", "unrestricted", "urs", "any", "r"}

        normalized = []
        for sign in v:
            token = str(sign).strip().lower().replace(" ", "")
            if token in free_aliases:
                normalized.append("free")
            elif token in nonneg_aliases or token == "":
                normalized.append("nonnegative")
            else:
                raise ValueError(
                    f"Biến '{sign}' không hợp lệ. Chỉ cho phép nonnegative hoặc free."
                )

        return normalized

router = APIRouter()

MODE_LIMITS = {
    "learning": {
        "max_vars": 24,
        "max_constraints": 40,
        "max_matrix_cells": 720,
    },
    "production": {
        "max_vars": 200,
        "max_constraints": 400,
        "max_matrix_cells": 40000,
    },
}

SOFT_TIMEOUT_SECONDS = {
    "learning": 6.0,
    "production": 4.0,
}


def _enforce_runtime_guardrails(mode: str, n_vars: int, n_constraints: int):
    limits = MODE_LIMITS.get(mode, MODE_LIMITS["learning"])
    cells = n_vars * n_constraints

    if n_vars > limits["max_vars"]:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Bài toán có {n_vars} biến, vượt giới hạn {limits['max_vars']} cho mode '{mode}'. "
                "Hãy chuyển sang production mode hoặc giảm kích thước mô hình."
            ),
        )

    if n_constraints > limits["max_constraints"]:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Bài toán có {n_constraints} ràng buộc, vượt giới hạn {limits['max_constraints']} cho mode '{mode}'. "
                "Hãy chuyển sang production mode hoặc giảm số ràng buộc."
            ),
        )

    if cells > limits["max_matrix_cells"]:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Kích thước ma trận ({n_vars}x{n_constraints} = {cells}) vượt ngưỡng {limits['max_matrix_cells']} cho mode '{mode}'. "
                "Vui lòng rút gọn bài toán hoặc dùng mode phù hợp."
            ),
        )

@router.post("/api/v1/simplex/solve")
async def solve_simplex(req: SimplexRequest):
    # 1. Validation Logic: Kích thước mảng
    num_vars = len(req.objective)
    for i, constraint in enumerate(req.constraints):
        if len(constraint) != num_vars:
            raise HTTPException(status_code=400, detail=f"Mặt cắt ma trận ràng buộc {i+1} không khớp với số biến mục tiêu.")
            
    if len(req.types) != len(req.constraints) or len(req.rhs) != len(req.constraints):
         raise HTTPException(status_code=400, detail="Độ dài mảng 'types' hoặc 'rhs' không khớp với số lượng dòng của 'constraints'.")

    if req.variable_signs is not None and len(req.variable_signs) != num_vars:
        raise HTTPException(
            status_code=400,
            detail="Độ dài mảng 'variable_signs' phải bằng số lượng biến trong objective.",
        )

    _enforce_runtime_guardrails(req.mode, num_vars, len(req.constraints))
    
    # Chuẩn bị model chuẩn hóa ở đây:
    try:
        parsed = parse_and_validate(
            req.objective,
            req.constraints,
            req.types,
            req.rhs,
            req.goal,
            req.variable_signs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    normalized_model = {
        "goal": parsed.get("goal"),
        "objective": parsed.get("objective", []),
        "constraints": parsed.get("constraints", []),
        "types": parsed.get("types", []),
        "decision_var_names": parsed.get("decision_var_names", []),
    }
    
    # 2. Rẽ nhánh theo mode
    if req.mode == "learning":
        init_dict = build_standard_form(
            parsed["objective"],
            parsed["constraints"],
            parsed["types"],
            parsed["goal"],
            decision_var_names=parsed.get("decision_var_names"),
        )

        try:
            steps = await asyncio.wait_for(
                asyncio.to_thread(run_full_tableau_with_snapshots, init_dict),
                timeout=SOFT_TIMEOUT_SECONDS["learning"],
            )
        except TimeoutError as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Learning mode quá tải thời gian xử lý cho mô hình hiện tại. "
                    "Hãy thử production mode hoặc giảm số biến/ràng buộc."
                ),
            ) from exc

        return {
            "status": "success", 
            "mode": "learning", 
            "message": "Sẵn sàng chạy chế độ Snapshot (Step-by-step)",
            "steps": steps, # Array của các snapshots
            "var_names": steps[0].get("var_names", []) if steps else init_dict.get("var_names", []),
            "normalization": parsed.get("normalization", {}),
            "normalized_model": normalized_model,
        }
        
    elif req.mode == "production":
        init_dict = build_standard_form(
            parsed["objective"],
            parsed["constraints"],
            parsed["types"],
            parsed["goal"],
            decision_var_names=parsed.get("decision_var_names"),
        )

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(run_revised_simplex, init_dict),
                timeout=SOFT_TIMEOUT_SECONDS["production"],
            )
        except TimeoutError as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Production mode quá tải thời gian xử lý cho mô hình hiện tại. "
                    "Vui lòng giảm kích thước mô hình hoặc thử lại với dữ liệu gọn hơn."
                ),
            ) from exc

        top_status = "success" if result.get("status") != "not_implemented" else "not_implemented"
        return {
            "status": top_status,
            "mode": "production",
            "message": "Production mode executed with compact revised-simplex result.",
            "result": result,
            "normalization": parsed.get("normalization", {}),
            "normalized_model": normalized_model,
        }
