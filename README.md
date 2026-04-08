# Hybrid Simplex Solver

Tai lieu tong hop chinh thuc cua du an.

## 1) Mo ta ngan

He thong giai bai toan Quy hoach Tuyen tinh (Linear Programming) bang Simplex, ho tro 2 che do:

- learning: tra ve toan bo cac buoc giai de hoc tap (snapshot tung bang, pivot, ratio, giai thich).
- production: tra ve ket qua gon va nhanh cho van hanh (khong tra ve mang steps lon).

He thong duoc tach lop ro rang:

- Backend API: FastAPI
- Frontend UI: Dash + Bootstrap + KaTeX
- Legacy code: luu de tham khao va doi chieu

## 2) Ngon ngu va thu vien su dung

### 2.1 Ngon ngu

- Python 3.12+
- Bash (script van hanh va benchmark)

### 2.2 Backend libraries

Theo [backend/requirements.txt](backend/requirements.txt):

- fastapi
- uvicorn
- pydantic
- numpy

### 2.3 Frontend libraries

Theo [frontend/requirements.txt](frontend/requirements.txt):

- dash
- dash-bootstrap-components
- dash-katex
- httpx
- numpy

### 2.4 Kiem thu

Theo [requirements-dev.txt](requirements-dev.txt):

- pytest

## 3) Giai thuat va pipeline

### 3.1 Stage 1 - Parser + Chuan hoa + Presolve

- Dong bo muc tieu max/min noi bo.
- Chuan hoa RHS (neu b_i < 0 thi nhan -1 ca dong va dao dau bat dang thuc).
- Ho tro bien tu do: x = x_plus - x_minus.
- Presolve co ban:
  - scaling theo dong,
  - loai rang buoc du thua,
  - phat hien mau thuan som.

File chinh: [backend/algorithms/stage1_parser.py](backend/algorithms/stage1_parser.py)

### 3.2 Stage 2 - Dua ve dang chuan va khoi tao 2 pha

- Tao slack/surplus/artificial.
- Doi co so tu nhien neu co.
- Khoi tao tableau phu hop cho pha 1/pha 2.

File chinh: [backend/algorithms/stage2_standardizer.py](backend/algorithms/stage2_standardizer.py)

### 3.3 Stage 3 - Full Tableau (learning mode)

- Vong lap pivot day du.
- Ratio test.
- Gauss-Jordan.
- Snapshot JSON-safe cho frontend.
- Co tich hop Bland tie-break khi suy bien.

File chinh: [backend/algorithms/stage3_full_tableau.py](backend/algorithms/stage3_full_tableau.py)

### 3.4 Stage 4 - Bland rule

- Chon bien vao/ra theo thu tu chi so khi co tie.
- Muc tieu: tranh cycling.

File chinh: [backend/algorithms/stage4_bland_rules.py](backend/algorithms/stage4_bland_rules.py)

### 3.5 Stage 5 - Revised simplex (production mode)

- Giai he theo huong revised simplex.
- Tang on dinh so hoc bang stable solve + fallback least squares.
- Tra output gon + sensitivity report.

File chinh: [backend/algorithms/stage5_revised_simplex.py](backend/algorithms/stage5_revised_simplex.py)

## 4) Dieu huong che do giai

- learning: Stage 1 -> Stage 2 -> Stage 3
- production: Stage 1 -> Stage 4 -> Stage 5

Duoc xu ly tai [backend/api/simplex_router.py](backend/api/simplex_router.py)

## 5) API contract

### 5.1 Endpoint

- POST /api/v1/simplex/solve

### 5.2 Request payload

```json
{
  "mode": "learning",
  "goal": "max",
  "objective": [3, 2],
  "constraints": [[2, 1], [1, 1]],
  "types": ["<=", "<="],
  "rhs": [100, 80],
  "variable_signs": ["nonnegative", "nonnegative"]
}
```

### 5.3 Learning response (tom tat)

- status, mode, message
- steps[] (step-by-step)
- var_names
- normalization
- normalized_model

### 5.4 Production response (tom tat)

- status, mode, message
- result:
  - status
  - solution_map
  - objective_value
  - iterations
  - termination_reason
  - engine
  - sensitivity (reduced_costs, dual_prices, binding_constraints)
- normalization
- normalized_model

## 6) Guardrails runtime

Tai [backend/api/simplex_router.py](backend/api/simplex_router.py):

- Gioi han kich thuoc theo mode:
  - learning: toi da 24 bien, 40 rang buoc, 720 o ma tran.
  - production: toi da 200 bien, 400 rang buoc, 40000 o ma tran.
- Soft timeout:
  - learning: 6 giay
  - production: 4 giay
- Loi than thien khi qua tai (HTTP 413/503).

## 7) Frontend va explainability

Thanh phan chinh:

- [frontend/layout.py](frontend/layout.py): bo cuc giao dien va control.
- [frontend/callbacks.py](frontend/callbacks.py): dong bo input, goi API, render ket qua table/algebra/production.
- [frontend/api_client.py](frontend/api_client.py): HTTP client den backend.

Diem noi bat:

- Hien thi bang Simplex co pivot/ratio.
- Giai thich Dai so theo 2 muc do.
- Tach ro Pha 1 / Pha 2.
- Hien thi thong tin chuan hoa khi can.
- Ho tro bat/tat card mo hinh da chuan hoa.

## 8) Cau truc thu muc

```text
.
├─ backend/
│  ├─ api/
│  ├─ algorithms/
│  ├─ utils/
│  └─ main.py
├─ frontend/
│  ├─ assets/
│  ├─ app.py
│  ├─ callbacks.py
│  ├─ layout.py
│  └─ api_client.py
├─ scripts/
│  ├─ dev_up.sh
│  ├─ test_smoke.sh
│  ├─ benchmark_modes.sh
│  └─ benchmark_modes.py
├─ tests/
│  └─ smoke/
└─ legacy/
   └─ old_system/
```

## 9) Cai dat va chay du an

### 9.1 Tao moi truong

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 9.2 Chay nhanh ca backend + frontend

```bash
source .venv/bin/activate
./scripts/dev_up.sh
```

### 9.3 Chay rieng backend

```bash
source .venv/bin/activate
cd backend
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### 9.4 Chay rieng frontend

```bash
source .venv/bin/activate
python frontend/app.py
```

## 10) Kiem thu va benchmark

### 10.1 Smoke tests

```bash
source .venv/bin/activate
./scripts/test_smoke.sh
```

### 10.2 Chay benchmark learning vs production

```bash
source .venv/bin/activate
./scripts/benchmark_modes.sh --n-vars 24 --extra-constraints 28 --cases 6
```

## 11) Bien moi truong quan trong

### 11.1 Frontend -> Backend API

- SIMPLEX_API_BASE_URL
- SIMPLEX_API_SOLVE_PATH
- SIMPLEX_API_TIMEOUT

### 11.2 Frontend runtime

- FRONTEND_HOST
- FRONTEND_PORT
- FRONTEND_DEBUG
- SIMPLEX_UI_MAX_DIM

### 11.3 script dev_up

- BACKEND_HOST
- BACKEND_PORT
- FRONTEND_HOST
- FRONTEND_PORT

## 12) Tai lieu bo sung

- Danh muc luu do bao cao (chi liet ke): [DANH_MUC_LUU_DO_BAO_CAO.md](DANH_MUC_LUU_DO_BAO_CAO.md)

## 13) Trang thai du an

He thong da hoan thien theo scope hien tai:

- learning mode hoat dong on dinh, co day du explainability.
- production mode hoat dong voi ket qua compact + sensitivity.
- guardrails runtime va smoke test da duoc tich hop.

