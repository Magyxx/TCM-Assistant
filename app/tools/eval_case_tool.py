from __future__ import annotations

from typing import Any, Dict


def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    case = payload.get("case") or {}
    turns = case.get("turns") if isinstance(case, dict) else None
    expected = case.get("expected") if isinstance(case, dict) else None
    return {
        "case_valid": isinstance(turns, list) and bool(turns),
        "turn_count": len(turns) if isinstance(turns, list) else 0,
        "has_expected": isinstance(expected, dict),
        "diagnosis_system": False,
    }
