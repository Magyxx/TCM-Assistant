from __future__ import annotations

import json
from typing import Any

from app.api.redaction import redact_secrets
from app.api.report_audit import audit_report, contains_secret
from app.observability.events import redacted_input_hash, utc_now
from app.report.safety import check_report_safety


REPORT_AUDIT_SCHEMA_VERSION = "p1_f5_report_audit_v1"


def _plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _redacted_json(value: Any) -> str:
    return json.dumps(redact_secrets(_plain(value)), ensure_ascii=False, sort_keys=True, default=str)


def _visible_text(value: Any) -> str:
    plain = _plain(value)
    if isinstance(plain, dict):
        visible = {
            key: item
            for key, item in plain.items()
            if key not in {"metadata", "evidence_pack", "evidence", "p1_evidence_pack"}
        }
        return _redacted_json(visible)
    return _redacted_json(plain)


def _has_safety_disclaimer(value: Any) -> bool:
    text = _visible_text(value).lower()
    return any(
        marker in text
        for marker in [
            "does not provide a diagnosis",
            "not a diagnosis",
            "clinician judgment",
            "\u4e0d\u6784\u6210\u8bca\u65ad",
            "\u4e0d\u80fd\u66ff\u4ee3\u533b\u751f",
            "\u4ec5\u7528\u4e8e\u95ee\u8bca\u4fe1\u606f\u6574\u7406",
        ]
    )


def build_report_audit(
    report: Any,
    state: Any = None,
    *,
    route: str,
    session_id: str | None = None,
    trace_id: str | None = None,
    ready: bool | None = None,
) -> dict[str, Any]:
    plain_report = _plain(report)
    plain_state = _plain(state) if state is not None else None
    api_audit = audit_report(plain_report, plain_state)
    p1_safety = check_report_safety(_visible_text(plain_report))
    no_secret = not contains_secret(plain_report) and not contains_secret(plain_state)
    safety_disclaimer_present = _has_safety_disclaimer(plain_report)
    structure_present = plain_report not in (None, "", [], {})
    flag_codes = [
        str(item.get("code"))
        for item in api_audit.get("flags", [])
        if isinstance(item, dict) and item.get("code")
    ]
    violations = list(dict.fromkeys([*flag_codes, *p1_safety.violations]))
    checks = {
        "structure_present": structure_present,
        "api_report_audit_passed": bool(api_audit.get("passed")),
        "p1_report_safety_passed": bool(p1_safety.ok),
        "no_secret": no_secret,
        "safety_disclaimer_present": safety_disclaimer_present,
    }
    passed = all(checks.values())
    return {
        "schema_version": REPORT_AUDIT_SCHEMA_VERSION,
        "status": "ok" if passed else "failed",
        "passed": passed,
        "checked_at": utc_now(),
        "session_id": session_id,
        "trace_id": trace_id,
        "route": route,
        "ready": ready,
        "checks": checks,
        "violations": violations,
        "api_audit_rules": redact_secrets(api_audit.get("rules") or {}),
        "api_audit_flags": redact_secrets(api_audit.get("flags") or []),
        "redacted_report_hash": redacted_input_hash(_redacted_json(plain_report)),
        "redacted_state_hash": redacted_input_hash(_redacted_json(plain_state)) if plain_state is not None else "",
    }
