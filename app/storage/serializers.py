from __future__ import annotations

import json
from typing import Any

from app.api.redaction import redact_secrets


def to_json_text(value: Any, *, redact: bool = True) -> str:
    payload = redact_secrets(value) if redact else value
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def from_json_text(value: str | None, default: Any = None) -> Any:
    if value is None:
        return default
    return json.loads(value)


def model_to_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return value
    return {"value": value}
