from __future__ import annotations

from typing import Any, Dict

from app.api.report_validator import validate_report


def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    return validate_report(payload.get("report"), payload.get("state"))
