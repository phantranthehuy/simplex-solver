"""
api_client.py
-------------
HTTP client utilities for calling the decoupled FastAPI simplex backend.
"""

import os
import logging
from typing import Any, Dict, Optional, Tuple

import httpx


logger = logging.getLogger(__name__)


def _build_solve_url() -> str:
    base = os.getenv("SIMPLEX_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    path = os.getenv("SIMPLEX_API_SOLVE_PATH", "/api/v1/simplex/solve")
    if not path.startswith("/"):
        path = "/" + path
    return f"{base}{path}"


def request_solver_result(payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Send a solve request to backend and return (json_data, error_message).

    Returns
    -------
    (dict, None) on success
    (None, str) on failure
    """
    url = _build_solve_url()
    timeout_sec = float(os.getenv("SIMPLEX_API_TIMEOUT", "30"))
    logger.debug("Sending simplex request to %s with mode=%s", url, payload.get("mode"))

    try:
        response = httpx.post(url, json=payload, timeout=timeout_sec)
    except httpx.RequestError as exc:
        logger.exception("Failed request to simplex backend")
        return None, f"Không kết nối được backend tại {url}. Chi tiết: {exc}"

    try:
        data = response.json()
    except ValueError:
        text_preview = response.text[:400] if response.text else "<empty>"
        return None, (
            f"Backend trả về dữ liệu không phải JSON (status={response.status_code}). "
            f"Body: {text_preview}"
        )

    if response.status_code >= 400:
        detail = data.get("detail") if isinstance(data, dict) else data
        logger.error("Backend returned error status=%s detail=%s", response.status_code, detail)
        return None, f"Backend lỗi (status={response.status_code}): {detail}"

    if not isinstance(data, dict):
        logger.error("Backend response root is not dict: %s", type(data))
        return None, "Backend trả về sai định dạng: cần một JSON object ở mức root."

    logger.debug("Simplex request succeeded with keys=%s", list(data.keys()))

    return data, None
