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


def _is_json_response(response: httpx.Response) -> bool:
    content_type = (response.headers.get("content-type") or "").lower()
    return "application/json" in content_type or "+json" in content_type


def _safe_preview(text: str, limit: int = 180) -> str:
    if not text:
        return "<empty>"
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[:limit] + "..."


def _format_http_error(status_code: int) -> str:
    if status_code in {502, 503, 504}:
        return (
            f"Backend tạm thời không sẵn sàng (status={status_code}). "
            "Vui lòng thử lại sau vài giây."
        )
    return f"Backend lỗi (status={status_code})."


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
    retry_count = max(0, int(os.getenv("SIMPLEX_API_RETRIES", "1")))
    max_attempts = retry_count + 1
    retryable_statuses = {502, 503, 504}
    logger.debug("Sending simplex request to %s with mode=%s", url, payload.get("mode"))

    response: Optional[httpx.Response] = None
    last_error: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = httpx.post(
                url,
                json=payload,
                timeout=timeout_sec,
                headers={"Accept": "application/json"},
            )
            if response.status_code in retryable_statuses and attempt < max_attempts:
                logger.warning(
                    "Retrying simplex request due to status=%s (attempt %s/%s)",
                    response.status_code,
                    attempt,
                    max_attempts,
                )
                continue
            break
        except httpx.RequestError as exc:
            last_error = exc
            if attempt < max_attempts:
                logger.warning(
                    "Retrying simplex request after network error (attempt %s/%s): %s",
                    attempt,
                    max_attempts,
                    exc,
                )
                continue
            logger.exception("Failed request to simplex backend")
            return None, f"Không kết nối được backend tại {url}. Chi tiết: {exc}"

    if response is None:
        err_text = str(last_error) if last_error else "unknown error"
        logger.error("Simplex request failed without response: %s", err_text)
        return None, f"Không nhận được phản hồi từ backend tại {url}."

    data: Any = None
    if _is_json_response(response):
        try:
            data = response.json()
        except ValueError:
            logger.error(
                "Response advertises JSON but parsing failed. status=%s body_preview=%s",
                response.status_code,
                _safe_preview(response.text),
            )

    if response.status_code >= 400:
        if isinstance(data, dict):
            detail = data.get("detail") or data.get("message") or data
            logger.error("Backend returned error status=%s detail=%s", response.status_code, detail)
            return None, f"Backend lỗi (status={response.status_code}): {detail}"

        logger.error(
            "Backend returned non-JSON error status=%s content_type=%s body_preview=%s",
            response.status_code,
            response.headers.get("content-type"),
            _safe_preview(response.text),
        )
        return None, _format_http_error(response.status_code)

    if data is None:
        logger.error(
            "Backend success response is not JSON. status=%s content_type=%s body_preview=%s",
            response.status_code,
            response.headers.get("content-type"),
            _safe_preview(response.text),
        )
        return None, (
            f"Backend trả về dữ liệu không phải JSON (status={response.status_code}). "
            "Vui lòng kiểm tra service backend."
        )

    if not isinstance(data, dict):
        logger.error("Backend response root is not dict: %s", type(data))
        return None, "Backend trả về sai định dạng: cần một JSON object ở mức root."

    logger.debug("Simplex request succeeded with keys=%s", list(data.keys()))

    return data, None
