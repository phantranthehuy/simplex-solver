import numpy as np

def float_to_pretty_string(val: float) -> str:
    """Xóa số `.0` thừa cho đẹp bảng."""
    if np.isinf(val):
        return "\\infty"
    if np.isnan(val):
        return "-"
    if float(val).is_integer():
        return str(int(val))
    return f"{val:.4g}"

def generate_katex_step(entering_var: str, leaving_var: str) -> str:
    """Tạo chuỗi KaTeX giải thích biến vào/ra để UI đẩy vào thư viện render."""
    if not entering_var or not leaving_var:
        return "\\text{Đã tìm thấy nghiệm tối ưu hoặc không thể pivot}"
    return f"\\text{{Biến vào }} {entering_var}, \\text{{ Biến ra }} {leaving_var}"
