from __future__ import annotations

import json
from typing import Any, Optional

from app.api.report_audit import (
    BOUNDARY_HINTS,
    FORBIDDEN_PHRASES,
    audit_report,
    contains_secret,
    _to_plain as _audit_to_plain,
)
from app.api.redaction import redact_secret_text
from app.schemas.report_schemas import FinalReport


TRIAGE_VALUES = {"observe", "followup", "urgent_visit"}
FINAL_REPORT_FIELDS = tuple(
    field
    for field in FinalReport.model_fields.keys()
    if field
    not in {
        "safety_disclaimer",
        "evidence_citations",
        "evidence_ids",
        "citation_coverage",
    }
)
STRING_FIELDS = ("summary", "impression")
LIST_STRING_FIELDS = ("advice", "missing_core_fields")
BOOL_FIELDS = ("info_complete", "followup_needed")
NO_DIAGNOSIS_PHRASES = (
    *FORBIDDEN_PHRASES["diagnosis_phrase"],
    *FORBIDDEN_PHRASES["confirmed_diagnosis_phrase"],
)
NO_PRESCRIPTION_PHRASES = FORBIDDEN_PHRASES["prescription_phrase"]
NO_TREATMENT_PLAN_PHRASES = FORBIDDEN_PHRASES["treatment_plan_phrase"]
UNSUPPORTED_URGENT_PHRASES = (
    "\u5f53\u524d\u5df2\u51fa\u73b0\u9ad8\u98ce\u9669\u4fe1\u53f7",
    "\u76ee\u524d\u5df2\u51fa\u73b0\u9ad8\u98ce\u9669\u4fe1\u53f7",
    "\u5df2\u51fa\u73b0\u9700\u8981\u8b66\u60d5\u7684\u98ce\u9669\u4fe1\u53f7",
    "\u5efa\u8bae\u5c3d\u5feb\u524d\u5f80\u7ebf\u4e0b\u533b\u7597\u673a\u6784\u5c31\u8bca",
)


def _base_result() -> dict[str, Any]:
    return {
        "passed": True,
        "errors": [],
        "warnings": [],
        "checks": {
            "json_serializable": False,
            "structure": False,
            "safety_audit": False,
            "no_secret": False,
            "no_diagnosis": False,
            "no_prescription": False,
            "no_treatment_plan": False,
            "state_supported": False,
        },
    }


def _redact_output(value: Any) -> Any:
    if isinstance(value, str):
        return redact_secret_text(value)
    if isinstance(value, list):
        return [_redact_output(item) for item in value]
    if isinstance(value, tuple):
        return [_redact_output(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact_output(item) for key, item in value.items()}
    return value


def _fail(result: dict[str, Any], code: str, message: str, details: Any = None) -> None:
    result["passed"] = False
    item: dict[str, Any] = {
        "code": code,
        "message": redact_secret_text(str(message)),
    }
    if details is not None:
        item["details"] = _redact_output(details)
    result["errors"].append(item)


def _warn(result: dict[str, Any], code: str, message: str, details: Any = None) -> None:
    item: dict[str, Any] = {
        "code": code,
        "message": redact_secret_text(str(message)),
    }
    if details is not None:
        item["details"] = _redact_output(details)
    result["warnings"].append(item)


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _visible_report_content(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {
            key: _visible_report_content(value)
            for key, value in payload.items()
            if key != "metadata"
        }
    if isinstance(payload, list):
        return [_visible_report_content(item) for item in payload]
    return payload


def _extract_report_payload(value: Any) -> tuple[Any, str]:
    plain = _audit_to_plain(value)
    if isinstance(plain, dict):
        if "report_json" in plain:
            return plain.get("report_json"), "report_json"
        if "final_report" in plain:
            return plain.get("final_report"), "final_report"
    return plain, "self"


def _extract_state_body(value: Any) -> Optional[dict[str, Any]]:
    if value is None:
        return None
    plain = _audit_to_plain(value)
    if not isinstance(plain, dict):
        return None
    state_body = plain.get("state")
    if isinstance(state_body, dict):
        return state_body
    return plain


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _has_boundary_hint(text: str) -> bool:
    return any(hint in text for hint in BOUNDARY_HINTS)


def _matched_phrases(text: str, phrases: tuple[str, ...]) -> list[str]:
    return [phrase for phrase in phrases if phrase in text]


def _validate_structure(result: dict[str, Any], payload: Any) -> None:
    if payload is None:
        _fail(result, "report_none", "report must not be None.")
        return
    if payload in ("", [], {}):
        _fail(result, "report_empty", "report must not be empty.")
        return

    if isinstance(payload, str):
        if not payload.strip():
            _fail(result, "report_empty_string", "report string must not be blank.")
            return
        result["checks"]["structure"] = True
        return

    if isinstance(payload, list):
        if not payload:
            _fail(result, "report_empty_list", "report list must not be empty.")
            return
        if any(item in (None, "", [], {}) for item in payload):
            _fail(result, "report_list_contains_empty_item", "report list contains an empty item.")
            return
        result["checks"]["structure"] = True
        return

    if not isinstance(payload, dict):
        _fail(result, "report_unsupported_type", "report must be a dict, list, or string.")
        return

    missing = [field for field in FINAL_REPORT_FIELDS if field not in payload]
    if missing:
        _fail(result, "report_required_fields_missing", "report missing required fields.", missing)

    field_errors: list[str] = []
    for field in STRING_FIELDS:
        if field in payload and (not isinstance(payload[field], str) or not payload[field].strip()):
            field_errors.append(f"{field} must be a non-empty string.")
    for field in LIST_STRING_FIELDS:
        if field in payload and not _is_string_list(payload[field]):
            field_errors.append(f"{field} must be a list of strings.")
    if "triage_level" in payload and payload["triage_level"] not in TRIAGE_VALUES:
        field_errors.append("triage_level has an invalid value.")
    for field in BOOL_FIELDS:
        if field in payload and not isinstance(payload[field], bool):
            field_errors.append(f"{field} must be boolean.")
    if "metadata" in payload and not isinstance(payload["metadata"], dict):
        field_errors.append("metadata must be an object.")

    for error in field_errors:
        _fail(result, "report_field_type_invalid", error)

    if not missing and not field_errors:
        result["checks"]["structure"] = True


def _missing_core_fields(state: dict[str, Any]) -> list[str]:
    explicit = state.get("missing_core_fields")
    if _is_string_list(explicit):
        return list(explicit)
    final_report = state.get("final_report")
    if isinstance(final_report, dict) and _is_string_list(final_report.get("missing_core_fields")):
        return list(final_report["missing_core_fields"])

    missing: list[str] = []
    if not state.get("chief_complaint"):
        missing.append("chief_complaint")
    if not state.get("duration"):
        missing.append("duration")
    if state.get("symptoms_status") == "unknown":
        missing.append("symptoms_status")
    if state.get("risk_flags_status") == "unknown":
        missing.append("risk_flags_status")
    return missing


def _validate_state_support(
    result: dict[str, Any],
    payload: Any,
    state: Any,
    report_text: str,
) -> None:
    state_body = _extract_state_body(state)
    if state_body is None:
        result["checks"]["state_supported"] = True
        _warn(result, "state_not_provided", "state-supported checks were skipped.")
        return

    if not isinstance(state_body, dict):
        _fail(result, "state_invalid", "state must be an object when provided.")
        return

    risk_status = state_body.get("risk_flags_status")
    missing = _missing_core_fields(state_body)
    triage = payload.get("triage_level") if isinstance(payload, dict) else None
    info_complete = payload.get("info_complete") if isinstance(payload, dict) else None
    followup_needed = payload.get("followup_needed") if isinstance(payload, dict) else None
    reported_missing = payload.get("missing_core_fields") if isinstance(payload, dict) else None
    supported = True

    if risk_status == "present":
        urgent_context = triage == "urgent_visit" or "urgent_visit" in report_text or "\u5c31\u533b" in report_text
        if not urgent_context:
            supported = False
            _fail(
                result,
                "red_flag_weakened",
                "state has present risk flags but report does not preserve urgent context.",
            )
        if triage is not None and triage != "urgent_visit":
            supported = False
            _fail(result, "red_flag_triage_weakened", "urgent state requires urgent_visit triage.")
    elif triage == "urgent_visit":
        supported = False
        _fail(result, "unsupported_urgent_triage", "urgent_visit triage is not supported by state.")
    elif any(phrase in report_text for phrase in UNSUPPORTED_URGENT_PHRASES):
        supported = False
        _fail(result, "unsupported_urgent_assertion", "report makes a strong urgent assertion unsupported by state.")

    if missing and risk_status != "present" and isinstance(payload, dict):
        if info_complete is True:
            supported = False
            _fail(result, "low_info_claims_complete", "report marks incomplete state as complete.", missing)
        if followup_needed is not True:
            supported = False
            _fail(result, "low_info_followup_missing", "incomplete state requires followup_needed=true.")
        if not _is_string_list(reported_missing) or not reported_missing:
            supported = False
            _fail(result, "low_info_missing_fields_absent", "report must expose missing fields for incomplete state.")

    if supported:
        result["checks"]["state_supported"] = True


def validate_report(report: Any, state: Any | None = None) -> dict[str, Any]:
    result = _base_result()
    payload, source = _extract_report_payload(report)
    result["source"] = source

    try:
        json.dumps(payload, ensure_ascii=False, sort_keys=True)
        result["checks"]["json_serializable"] = True
    except (TypeError, ValueError) as exc:
        _fail(result, "report_not_json_serializable", f"report is not JSON serializable: {type(exc).__name__}.")

    _validate_structure(result, payload)

    report_text = _json_text(payload)
    visible_report_text = _json_text(_visible_report_content(payload))
    audit = audit_report(payload, state)
    result["audit"] = audit
    if audit.get("passed") and _has_boundary_hint(report_text):
        result["checks"]["safety_audit"] = True
    else:
        if not audit.get("passed"):
            _fail(result, "report_safety_audit_failed", "report failed report_audit.", audit.get("flags"))
        if not _has_boundary_hint(report_text):
            _fail(result, "missing_safety_boundary_hint", "report must include a safety-boundary hint.")

    if contains_secret(payload):
        _fail(result, "secret_found", "report contains unredacted secret-like content.")
    else:
        result["checks"]["no_secret"] = True

    diagnosis_matches = _matched_phrases(report_text, NO_DIAGNOSIS_PHRASES)
    if diagnosis_matches:
        _fail(result, "diagnosis_phrase_found", "report contains diagnosis-like phrase.", diagnosis_matches)
    else:
        result["checks"]["no_diagnosis"] = True

    prescription_matches = _matched_phrases(report_text, NO_PRESCRIPTION_PHRASES)
    if prescription_matches:
        _fail(result, "prescription_phrase_found", "report contains prescription-like phrase.", prescription_matches)
    else:
        result["checks"]["no_prescription"] = True

    treatment_matches = _matched_phrases(report_text, NO_TREATMENT_PLAN_PHRASES)
    if treatment_matches:
        _fail(result, "treatment_plan_phrase_found", "report contains treatment-plan-like phrase.", treatment_matches)
    else:
        result["checks"]["no_treatment_plan"] = True

    _validate_state_support(result, payload, state, visible_report_text)

    result["passed"] = not result["errors"]
    return _redact_output(result)


def assert_report_valid(report: Any, state: Any | None = None) -> None:
    result = validate_report(report, state)
    if not result["passed"]:
        raise ValueError(json.dumps(result["errors"], ensure_ascii=False, sort_keys=True))


def validate_report_snapshot(snapshot: Any, state: Any | None = None) -> dict[str, Any]:
    plain = _audit_to_plain(snapshot)
    result = validate_report(plain, state)
    if isinstance(plain, dict):
        safety_flags = plain.get("safety_flags_json")
        result["snapshot"] = {
            "has_report_json": "report_json" in plain,
            "has_safety_flags_json": isinstance(safety_flags, dict),
            "stored_validator_present": isinstance(safety_flags, dict)
            and isinstance(safety_flags.get("validator"), dict),
        }
    else:
        result["snapshot"] = {
            "has_report_json": False,
            "has_safety_flags_json": False,
            "stored_validator_present": False,
        }
    return _redact_output(result)
