from __future__ import annotations

from typing import Any

from app.api.redaction import redact_secret_text


def redact_preserving_schema(value: Any) -> Any:
    if isinstance(value, str):
        return redact_secret_text(value)
    if isinstance(value, list):
        return [redact_preserving_schema(item) for item in value]
    if isinstance(value, tuple):
        return [redact_preserving_schema(item) for item in value]
    if isinstance(value, dict):
        return {
            redact_secret_text(str(key)) if isinstance(key, str) else key: redact_preserving_schema(item)
            for key, item in value.items()
        }
    return value
