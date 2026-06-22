from __future__ import annotations

import json
import re
from typing import Any


REDACTED_SECRET = "[redacted-secret]"
REDACTED_SECRET_KEY = "[redacted-secret-key]"

SECRET_VALUE_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(
        r"\b[A-Z0-9_]*(?:API[_-]?KEY|SECRET|TOKEN)[A-Z0-9_]*\b\s*[:=]\s*[^,\s\"']+",
        re.IGNORECASE,
    ),
)

SECRET_KEY_PATTERN = re.compile(
    r"(?:api[_-]?key|secret|token|authorization|password)",
    re.IGNORECASE,
)


def redact_secret_text(value: str) -> str:
    redacted = value
    for pattern in SECRET_VALUE_PATTERNS:
        redacted = pattern.sub(REDACTED_SECRET, redacted)
    return redacted


def redact_secrets(value: Any) -> Any:
    if isinstance(value, str):
        return redact_secret_text(value)
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            safe_key = key
            if isinstance(key, str):
                safe_key = (
                    REDACTED_SECRET_KEY
                    if SECRET_KEY_PATTERN.search(key)
                    else redact_secret_text(key)
                )
            redacted[safe_key] = redact_secrets(item)
        return redacted
    return value


def dumps_redacted_json(value: Any) -> str:
    return json.dumps(redact_secrets(value), ensure_ascii=False, sort_keys=True)
