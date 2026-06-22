from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.api.errors import ApiError, TURN_REJECTED
from app.api.redaction import SECRET_KEY_PATTERN, SECRET_VALUE_PATTERNS, redact_secrets


FORBIDDEN_PHRASES = {
    "diagnosis_phrase": ("\u8bca\u65ad\u4e3a",),
    "confirmed_diagnosis_phrase": ("\u786e\u8bca",),
    "prescription_phrase": ("\u5904\u65b9",),
    "treatment_plan_phrase": ("\u6cbb\u7597\u65b9\u6848",),
}

SUBSTITUTE_ADVICE_PHRASES = (
    "\u53ef\u4ee5\u66ff\u4ee3\u533b\u751f",
    "\u80fd\u591f\u66ff\u4ee3\u533b\u751f",
    "\u4e0d\u7528\u5c31\u533b",
    "\u65e0\u9700\u5c31\u533b",
    "\u4e0d\u5fc5\u5c31\u533b",
)

BOUNDARY_HINTS = (
    "\u4e0d\u662f\u8bca\u65ad",
    "\u4e0d\u4f5c\u4e3a\u8bca\u65ad",
    "\u4ec5\u7528\u4e8e\u95ee\u8bca\u4fe1\u606f\u6574\u7406",
    "\u4e0d\u80fd\u66ff\u4ee3\u533b\u751f",
    "not a diagnosis",
)

DRUG_DOSE_PATTERN = re.compile(
    r"\d+(?:\.\d+)?\s*(?:mg|g|ml|\u6beb\u514b|\u514b|\u6beb\u5347|"
    r"\u7247|\u7c92|\u4e38|\u888b|\u6ef4|\u6b21/\u65e5|bid|tid|qid)",
    re.IGNORECASE,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {str(key): _to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(item) for item in value]
    return value


def _text(value: Any) -> str:
    return json.dumps(_to_plain(value), ensure_ascii=False, sort_keys=True)


def contains_secret(value: Any) -> bool:
    text = _text(value)
    if any(pattern.search(text) for pattern in SECRET_VALUE_PATTERNS):
        return True
    if isinstance(value, dict):
        return any(
            SECRET_KEY_PATTERN.search(str(key)) or contains_secret(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(contains_secret(item) for item in value)
    return False


def _flag(code: str, message: str, matches: List[str] | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"code": code, "message": message}
    if matches:
        payload["matches"] = redact_secrets(matches)
    return payload


def audit_report(report: Any, state: Any = None) -> Dict[str, Any]:
    plain_report = _to_plain(report)
    plain_state = _to_plain(state) if state is not None else None
    text = _text(plain_report)
    flags: List[Dict[str, Any]] = []

    if plain_report in (None, "", [], {}):
        flags.append(_flag("empty_report", "Report snapshot is empty."))

    for code, phrases in FORBIDDEN_PHRASES.items():
        matches = [phrase for phrase in phrases if phrase in text]
        if matches:
            flags.append(_flag(code, "Report contains an out-of-bound medical phrase.", matches))

    substitute_matches = [phrase for phrase in SUBSTITUTE_ADVICE_PHRASES if phrase in text]
    if substitute_matches:
        flags.append(
            _flag(
                "substitute_medical_advice",
                "Report appears to substitute for clinician judgment.",
                substitute_matches,
            )
        )

    dose_matches = DRUG_DOSE_PATTERN.findall(text)
    if dose_matches:
        flags.append(
            _flag(
                "drug_dose_like",
                "Report contains medication-dose-like text.",
                [str(match) for match in dose_matches],
            )
        )

    if contains_secret(plain_report):
        flags.append(_flag("secret_like", "Report contains secret-like text."))

    state_text = _text(plain_state) if plain_state is not None else ""
    rules = {
        "forbidden_phrases_checked": sorted(FORBIDDEN_PHRASES),
        "drug_dose_pattern_checked": True,
        "credential_pattern_checked": True,
        "substitute_medical_advice_checked": True,
        "safety_boundary_hint_present": any(hint in text for hint in BOUNDARY_HINTS),
        "urgent_state_has_report_context": (
            "urgent_visit" not in state_text or "urgent_visit" in text or "\u5c31\u533b" in text
        ),
    }

    return {
        "passed": not flags,
        "flags": flags,
        "checked_at": _now_iso(),
        "rules": rules,
    }


def assert_report_safe(report: Any, state: Any = None) -> None:
    audit = audit_report(report, state)
    if not audit["passed"]:
        raise ApiError(
            TURN_REJECTED,
            status_code=409,
            message="Generated report failed safety audit.",
            details={"audit": audit},
        )
