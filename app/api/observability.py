from __future__ import annotations

import json
import re
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, TextIO
from uuid import uuid4

from app.api.runtime_config import RuntimeConfig, get_runtime_config


REDACTED = "[REDACTED]"
REDACTED_KEY = "[REDACTED_KEY]"
TRUNCATED = "[TRUNCATED]"
DEFAULT_MAX_TEXT_LENGTH = 160
LOG_LEVEL_ORDER = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}
EVENT_FIELDS = (
    "ts",
    "level",
    "event",
    "runtime_mode",
    "request_id",
    "session_id",
    "turn_id",
    "component",
    "status",
    "duration_ms",
    "message",
    "extra",
)
SENSITIVE_KEY_PATTERN = re.compile(
    r"(openai_api_key|api[_-]?key|password|secret|token|authorization|cookie)",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(
        r"\b[A-Z0-9_]*(?:API[_-]?KEY|SECRET|TOKEN|AUTHORIZATION|COOKIE|PASSWORD)[A-Z0-9_]*\b\s*[:=]\s*[^,\s\"']+",
        re.IGNORECASE,
    ),
)
USER_TEXT_KEYS = frozenset({"user_input", "input", "raw_input", "body", "prompt", "text"})
_REQUEST_ID_CTX: ContextVar[str | None] = ContextVar("tcm_request_id", default=None)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_request_id() -> str:
    return str(uuid4())


def normalize_request_id(value: str | None) -> str:
    if value is None or not value.strip():
        return generate_request_id()
    cleaned = value.strip()
    if len(cleaned) > 128:
        return cleaned[:128]
    return cleaned


def set_current_request_id(request_id: str | None) -> None:
    _REQUEST_ID_CTX.set(request_id)


def get_current_request_id() -> str | None:
    return _REQUEST_ID_CTX.get()


def _truncate(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    keep = max(0, max_length)
    return f"{value[:keep]}...{TRUNCATED}"


def redact_text(value: str, *, max_length: int = DEFAULT_MAX_TEXT_LENGTH) -> str:
    redacted = value
    for pattern in SECRET_VALUE_PATTERNS:
        redacted = pattern.sub(REDACTED, redacted)
    return _truncate(redacted, max_length)


def redact_observable_value(
    value: Any,
    *,
    redact_logs: bool = True,
    max_text_length: int = DEFAULT_MAX_TEXT_LENGTH,
    _key: str | None = None,
) -> Any:
    if _key and SENSITIVE_KEY_PATTERN.search(_key):
        if _key.lower().endswith("_present") and isinstance(value, bool):
            return value
        return REDACTED

    if isinstance(value, str):
        max_length = min(max_text_length, 80) if _key in USER_TEXT_KEYS else max_text_length
        safe_value = redact_text(value, max_length=max_length)
        if redact_logs and _key in USER_TEXT_KEYS:
            return _truncate(safe_value, min(max_length, 80))
        return safe_value
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            safe_key = (
                key_text
                if not SENSITIVE_KEY_PATTERN.search(key_text) or key_text.lower().endswith("_present")
                else REDACTED_KEY
            )
            redacted[safe_key] = redact_observable_value(
                item,
                redact_logs=redact_logs,
                max_text_length=max_text_length,
                _key=key_text,
            )
        return redacted
    if isinstance(value, list):
        return [
            redact_observable_value(
                item,
                redact_logs=redact_logs,
                max_text_length=max_text_length,
                _key=_key,
            )
            for item in value
        ]
    if isinstance(value, tuple):
        return [
            redact_observable_value(
                item,
                redact_logs=redact_logs,
                max_text_length=max_text_length,
                _key=_key,
            )
            for item in value
        ]
    return value


def should_emit(level: str, config: RuntimeConfig | None = None) -> bool:
    runtime_config = config or get_runtime_config()
    configured = LOG_LEVEL_ORDER.get(runtime_config.log_level.upper(), LOG_LEVEL_ORDER["INFO"])
    requested = LOG_LEVEL_ORDER.get(level.upper(), LOG_LEVEL_ORDER["INFO"])
    return requested >= configured


def make_log_event(
    event: str,
    *,
    level: str = "INFO",
    component: str = "api",
    status: str | None = None,
    request_id: str | None = None,
    session_id: str | None = None,
    turn_id: str | None = None,
    duration_ms: float | int | None = None,
    message: str | None = None,
    extra: dict[str, Any] | None = None,
    config: RuntimeConfig | None = None,
) -> dict[str, Any]:
    runtime_config = config or get_runtime_config()
    event_level = level.upper()
    safe_extra = redact_observable_value(
        extra or {},
        redact_logs=runtime_config.redact_logs,
    )
    safe_message = (
        redact_observable_value(message, redact_logs=runtime_config.redact_logs)
        if message is not None
        else None
    )
    payload = {
        "ts": utc_now_iso(),
        "level": event_level,
        "event": str(event),
        "runtime_mode": runtime_config.runtime_mode,
        "request_id": request_id or get_current_request_id(),
        "session_id": session_id,
        "turn_id": turn_id,
        "component": component,
        "status": status,
        "duration_ms": round(float(duration_ms), 3) if duration_ms is not None else None,
        "message": safe_message,
        "extra": safe_extra,
    }
    return {field: payload[field] for field in EVENT_FIELDS}


def emit_log_event(
    payload: dict[str, Any],
    *,
    stream: TextIO | None = None,
    config: RuntimeConfig | None = None,
) -> dict[str, Any]:
    runtime_config = config or get_runtime_config()
    if not should_emit(str(payload.get("level") or "INFO"), runtime_config):
        return payload
    target = stream or sys.stderr
    safe_payload = redact_observable_value(payload, redact_logs=runtime_config.redact_logs)
    target.write(json.dumps(safe_payload, ensure_ascii=False, sort_keys=True) + "\n")
    try:
        target.flush()
    except Exception:
        pass
    return payload


def log_event(
    event: str,
    *,
    level: str = "INFO",
    component: str = "api",
    status: str | None = None,
    request_id: str | None = None,
    session_id: str | None = None,
    turn_id: str | None = None,
    duration_ms: float | int | None = None,
    message: str | None = None,
    extra: dict[str, Any] | None = None,
    stream: TextIO | None = None,
    config: RuntimeConfig | None = None,
) -> dict[str, Any]:
    runtime_config = config or get_runtime_config()
    payload = make_log_event(
        event,
        level=level,
        component=component,
        status=status,
        request_id=request_id,
        session_id=session_id,
        turn_id=turn_id,
        duration_ms=duration_ms,
        message=message,
        extra=extra,
        config=runtime_config,
    )
    emit_log_event(payload, stream=stream, config=runtime_config)
    return payload
