# Hybrid Simplex Solver

Tài liệu tổng hợp chính thức của dự án.

## 1) Mô tả ngắn

Hệ thống giải bài toán Quy hoạch Tuyến tính (Linear Programming) bằng Simplex, hỗ trợ 2 chế độ:

- learning: trả về toàn bộ các bước giải để học tập (snapshot từng bảng, pivot, ratio, giải thích).
- production: trả về kết quả gọn và nhanh cho vận hành (không trả về mảng steps lớn).

Hệ thống được tách lớp rõ ràng:

- Backend API: FastAPI
- Frontend UI: Dash + Bootstrap + KaTeX
- Legacy code: lưu để tham khảo và đối chiếu

## 2) Ngôn ngữ và thư viện sử dụng

### 2.1 Ngôn ngữ

- Python 3.12+
- Bash (script vận hành và benchmark)

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

### 2.4 Kiểm thử

Theo [requirements-dev.txt](requirements-dev.txt):

- pytest

## 3) Giải thuật và pipeline

### 3.1 Stage 1 - Parser + Chuẩn hóa + Presolve

- Đồng bộ mục tiêu max/min nội bộ.
- Chuẩn hóa RHS (nếu b_i < 0 thì nhân -1 cả dòng và đảo dấu bất đẳng thức).
- Hỗ trợ biến tự do: x = x_plus - x_minus.
- Presolve cơ bản:
  - scaling theo dòng,
  - loại bỏ ràng buộc dư thừa,
  - phát hiện mâu thuẫn sớm.

File chính: [backend/algorithms/stage1_parser.py](backend/algorithms/stage1_parser.py)

### 3.2 Stage 2 - Đưa về dạng chuẩn và khởi tạo 2 pha

- Tạo slack/surplus/artificial.
- Đối cơ sở tự nhiên nếu có.
- Khởi tạo tableau phù hợp cho pha 1/pha 2.

File chính: [backend/algorithms/stage2_standardizer.py](backend/algorithms/stage2_standardizer.py)

### 3.3 Stage 3 - Full Tableau (learning mode)

- Vòng lặp pivot đầy đủ.
- Ratio test.
- Gauss-Jordan.
- Snapshot JSON-safe cho frontend.
- Có tích hợp Bland tie-break khi suy biến.

File chính: [backend/algorithms/stage3_full_tableau.py](backend/algorithms/stage3_full_tableau.py)

### 3.4 Stage 4 - Bland rule

- Chọn biến vào/ra theo thứ tự chỉ số khi có tie.
- Mục tiêu: tránh cycling.

File chính: [backend/algorithms/stage4_bland_rules.py](backend/algorithms/stage4_bland_rules.py)

### 3.5 Stage 5 - Revised simplex (production mode)

- Giải hệ theo hướng revised simplex.
- Tăng ổn định số học bằng stable solve + fallback least squares.
- Trả output gọn + sensitivity report.

File chính: [backend/algorithms/stage5_revised_simplex.py](backend/algorithms/stage5_revised_simplex.py)

## 4) Điều hướng chế độ giải

- learning: Stage 1 -> Stage 2 -> Stage 3
- production: Stage 1 -> Stage 4 -> Stage 5

Được xử lý tại [backend/api/simplex_router.py](backend/api/simplex_router.py)

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

### 5.3 Learning response (tóm tắt)

- status, mode, message
- steps[] (step-by-step)
- var_names
- normalization
- normalized_model

### 5.4 Production response (tóm tắt)

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

Tại [backend/api/simplex_router.py](backend/api/simplex_router.py):

- Giới hạn kích thước theo mode:
  - learning: tối đa 24 biến, 40 ràng buộc, 720 ô ma trận.
  - production: tối đa 200 biến, 400 ràng buộc, 40000 ô ma trận.
- Soft timeout:
  - learning: 6 giây
  - production: 4 giây
- Lỗi thân thiện khi quá tải (HTTP 413/503).

## 7) Frontend và explainability

Thành phần chính:

- [frontend/layout.py](frontend/layout.py): bộ cục giao diện và control.
- [frontend/callbacks.py](frontend/callbacks.py): đồng bộ input, gọi API, render kết quả table/algebra/production.
- [frontend/api_client.py](frontend/api_client.py): HTTP client đến backend.

Điểm nổi bật:

- Hiển thị bảng Simplex có pivot/ratio.
- Giải thích Đại số theo 2 mức độ.
- Tách rõ Pha 1 / Pha 2.
- Hiển thị thông tin chuẩn hóa khi cần.
- Hỗ trợ bật/tắt card mô hình đã chuẩn hóa.

## 8) Cấu trúc thư mục

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

## 9) Cài đặt và chạy dự án

### 9.1 Tạo môi trường

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 9.2 Chạy nhanh cả backend + frontend

```bash
source .venv/bin/activate
./scripts/dev_up.sh
```

### 9.3 Chạy riêng backend

```bash
source .venv/bin/activate
cd backend
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### 9.4 Chạy riêng frontend

```bash
source .venv/bin/activate
python frontend/app.py
```

## 10) Kiểm thử và benchmark

### 10.1 Smoke tests

```bash
source .venv/bin/activate
./scripts/test_smoke.sh
```

### 10.2 Chạy benchmark learning vs production

```bash
source .venv/bin/activate
./scripts/benchmark_modes.sh --n-vars 24 --extra-constraints 28 --cases 6
```

## 11) Biến môi trường quan trọng

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

## 12) Tài liệu bổ sung

- Danh mục lưu độ báo cáo (chi liet ke): [DANH_MUC_LUU_DO_BAO_CAO.md](DANH_MUC_LUU_DO_BAO_CAO.md)

## 13) Trạng thái dự án

Hệ thống đã hoàn thiện theo scope hiện tại:

- learning mode hoạt động ổn định, có đầy đủ explainability.
- production mode hoạt động với kết quả compact + sensitivity.
- guardrails runtime và smoke test đã được tích hợp.

## 14) Deploy lên Render

### 14.1 Cách nhanh bằng Blueprint

Repository đã có sẵn file `render.yaml` ở root để tạo đồng thời 2 web services:

- `simplex-backend` (FastAPI)
- `simplex-frontend` (Dash)

Các bước:

1. Push code lên GitHub.
2. Trên Render, chọn New + Blueprint và kết nối repo.
3. Render sẽ đọc `render.yaml` và tạo 2 services.
4. Sau khi backend lên xong, lấy URL backend dạng `https://...onrender.com`.
5. Vào service frontend, sửa env `SIMPLEX_API_BASE_URL` đúng URL backend rồi deploy lại frontend.

Lưu ý:

- Frontend đã được cập nhật để tự nhận cổng Render qua biến `PORT`.
- Giá trị placeholder trong `render.yaml` (`https://replace-with-your-backend-url.onrender.com`) bắt buộc phải thay bằng URL backend thật.

### 14.2 Cách tạo thủ công 2 services

Nếu không dùng Blueprint, tạo 2 Web Service riêng:

1. Backend service
  - Build Command: `pip install -r requirements.txt`
  - Start Command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
2. Frontend service
  - Build Command: `pip install -r requirements.txt`
  - Start Command: `python frontend/app.py`
  - Env bắt buộc:
    - `FRONTEND_HOST=0.0.0.0`
    - `FRONTEND_DEBUG=0`
    - `SIMPLEX_API_BASE_URL=https://<backend-service>.onrender.com`
    - `SIMPLEX_API_SOLVE_PATH=/api/v1/simplex/solve`
    - `SIMPLEX_API_TIMEOUT=30`
