from __future__ import annotations

import re
from typing import Any

from app.api.redaction import redact_secret_text


PII_PATTERNS = (
    re.compile(r"\b1[3-9]\d{9}\b"),
    re.compile(r"\b\d{15}(?:\d{2}[0-9Xx])?\b"),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
)


def contains_pii_text(value: str) -> bool:
    redacted = redact_secret_text(value)
    return any(pattern.search(redacted) for pattern in PII_PATTERNS)


def contains_pii(value: Any) -> bool:
    if isinstance(value, str):
        return contains_pii_text(value)
    if isinstance(value, dict):
        return any(contains_pii(key) or contains_pii(item) for key, item in value.items())
    if isinstance(value, (list, tuple, set)):
        return any(contains_pii(item) for item in value)
    return False


def preview_text(value: str, limit: int = 120) -> str:
    safe = redact_secret_text(value).strip()
    if len(safe) <= limit:
        return safe
    return f"{safe[:limit]}...[TRUNCATED]"


def assert_l4_safe(items: list[dict[str, Any]]) -> bool:
    for item in items:
        if item.get("contains_pii") or item.get("contains_raw_patient_text"):
            return False
        if contains_pii(item):
            return False
    return True
