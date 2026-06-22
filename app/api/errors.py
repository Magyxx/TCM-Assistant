from __future__ import annotations

import re
from typing import Any, Dict, Optional

from fastapi.responses import JSONResponse

from app.api.redaction import redact_secrets


INVALID_REQUEST = "INVALID_REQUEST"
SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
STATE_NOT_FOUND = "STATE_NOT_FOUND"
STORE_UNAVAILABLE = "STORE_UNAVAILABLE"
STATE_CORRUPTED = "STATE_CORRUPTED"
TURN_REJECTED = "TURN_REJECTED"
INTERNAL_ERROR = "INTERNAL_ERROR"


ERROR_MESSAGES = {
    INVALID_REQUEST: "Invalid request.",
    SESSION_NOT_FOUND: "Session not found.",
    STATE_NOT_FOUND: "Session state not found.",
    STORE_UNAVAILABLE: "SQLite store is unavailable.",
    STATE_CORRUPTED: "Session state is corrupted.",
    TURN_REJECTED: "Turn was rejected.",
    INTERNAL_ERROR: "Internal server error.",
}

ERROR_STATUS = {
    INVALID_REQUEST: 400,
    SESSION_NOT_FOUND: 404,
    STATE_NOT_FOUND: 500,
    STORE_UNAVAILABLE: 503,
    STATE_CORRUPTED: 500,
    TURN_REJECTED: 409,
    INTERNAL_ERROR: 500,
}


class ApiError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        message: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, ERROR_MESSAGES[INTERNAL_ERROR])
        self.status_code = status_code or ERROR_STATUS.get(code, ERROR_STATUS[INTERNAL_ERROR])
        self.details = details or {}
        super().__init__(self.message)


def _sanitize_text(value: str) -> str:
    value = redact_secrets(value)
    value = re.sub(r"[A-Za-z]:\\[^\s\"'}]+", "[redacted-path]", value)
    value = re.sub(r"\bFile \"[^\"]+\"", 'File "[redacted-path]"', value)
    value = re.sub(r"Traceback \(most recent call last\):.*", "[redacted-traceback]", value)
    return value


def sanitize_error_details(value: Any) -> Any:
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, list):
        return [sanitize_error_details(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_error_details(item) for item in value]
    if isinstance(value, dict):
        return {
            sanitize_error_details(key): sanitize_error_details(item)
            for key, item in value.items()
        }
    return value


def error_payload(
    code: str,
    *,
    message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": _sanitize_text(
                message or ERROR_MESSAGES.get(code, ERROR_MESSAGES[INTERNAL_ERROR])
            ),
            "details": sanitize_error_details(details or {}),
        }
    }


def error_response(
    code: str,
    *,
    status_code: Optional[int] = None,
    message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code or ERROR_STATUS.get(code, ERROR_STATUS[INTERNAL_ERROR]),
        content=error_payload(code, message=message, details=details),
    )
