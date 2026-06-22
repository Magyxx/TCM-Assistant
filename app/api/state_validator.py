from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

from pydantic import ValidationError

from app.api.report_audit import FORBIDDEN_PHRASES, contains_secret
from app.api.redaction import redact_secret_text
from app.api.sqlite_store import connect, initialize_database
from app.schemas.report_schemas import RunState


TRI_STATE_VALUES = {"unknown", "none", "present"}
TRIAGE_VALUES = {"observe", "followup", "urgent_visit"}
OPTIONAL_STRING_FIELDS = {
    "chief_complaint",
    "duration",
    "sleep",
    "appetite",
    "stool_urine",
    "next_question",
    "summary",
}
LIST_STRING_FIELDS = {
    "symptoms",
    "risk_flags",
    "risk_reasons",
    "triggered_rule_ids",
}
FORBIDDEN_STATE_PHRASES = tuple(
    dict.fromkeys(
        phrase
        for phrases in FORBIDDEN_PHRASES.values()
        for phrase in phrases
    )
)
REQUIRED_STATE_FIELDS = tuple(RunState.model_fields.keys())


def _base_result() -> dict[str, Any]:
    return {
        "passed": True,
        "errors": [],
        "warnings": [],
        "checks": {
            "json_serializable": False,
            "required_fields": False,
            "field_types": False,
            "state_version": False,
            "no_secret": False,
            "no_forbidden_medical_output": False,
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


def _fail(result: dict[str, Any], code: str, message: str) -> None:
    result["passed"] = False
    result["errors"].append(
        {
            "code": code,
            "message": redact_secret_text(str(message)),
        }
    )


def _warn(result: dict[str, Any], code: str, message: str) -> None:
    result["warnings"].append(
        {
            "code": code,
            "message": redact_secret_text(str(message)),
        }
    )


def _plain_state(state: Any) -> Any:
    if hasattr(state, "model_dump"):
        return state.model_dump()
    return state


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _has_forbidden_medical_output(value: Any) -> bool:
    text = _json_text(value)
    return any(phrase in text for phrase in FORBIDDEN_STATE_PHRASES)


def _is_optional_string(value: Any) -> bool:
    return value is None or isinstance(value, str)


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _validate_final_report_shape(report: Any) -> list[str]:
    errors: list[str] = []
    if report is None:
        return errors
    if not isinstance(report, dict):
        return ["final_report must be an object or null."]

    string_fields = ("summary", "impression")
    for field in string_fields:
        if field in report and not isinstance(report[field], str):
            errors.append(f"final_report.{field} must be a string.")

    if "advice" in report and not _is_string_list(report["advice"]):
        errors.append("final_report.advice must be a list of strings.")
    if "triage_level" in report and report["triage_level"] not in TRIAGE_VALUES:
        errors.append("final_report.triage_level has an invalid value.")
    if "info_complete" in report and not isinstance(report["info_complete"], bool):
        errors.append("final_report.info_complete must be boolean.")
    if "missing_core_fields" in report and not _is_string_list(report["missing_core_fields"]):
        errors.append("final_report.missing_core_fields must be a list of strings.")
    if "followup_needed" in report and not isinstance(report["followup_needed"], bool):
        errors.append("final_report.followup_needed must be boolean.")
    if "metadata" in report and not isinstance(report["metadata"], dict):
        errors.append("final_report.metadata must be an object.")
    return errors


def _state_version_value(state: dict[str, Any]) -> tuple[Optional[int], bool, Optional[str]]:
    if "state_version" not in state:
        fallback = state.get("turn_count")
        if isinstance(fallback, int) and fallback >= 0:
            return fallback, True, None
        return None, True, "state_version is missing and turn_count fallback is unavailable."

    raw = state.get("state_version")
    if not isinstance(raw, int) or isinstance(raw, bool):
        return None, False, "state_version must be a non-negative integer."
    if raw < 0:
        return None, False, "state_version must be non-negative."
    return raw, False, None


def validate_state(state: Any) -> dict[str, Any]:
    result = _base_result()
    plain = _plain_state(state)

    if plain is None:
        _fail(result, "state_none", "state must not be None.")
        return result
    if not isinstance(plain, dict):
        _fail(result, "state_not_object", "state must be a JSON object.")
        return result
    if not plain:
        _fail(result, "state_empty", "state must not be an empty object.")

    try:
        json.dumps(plain, ensure_ascii=False, sort_keys=True)
        result["checks"]["json_serializable"] = True
    except (TypeError, ValueError) as exc:
        _fail(result, "state_not_json_serializable", f"state is not JSON serializable: {type(exc).__name__}.")

    missing = [field for field in REQUIRED_STATE_FIELDS if field not in plain]
    if missing:
        _fail(result, "required_fields_missing", f"state missing required fields: {missing}.")
    else:
        result["checks"]["required_fields"] = True

    field_type_errors: list[str] = []
    for field in OPTIONAL_STRING_FIELDS:
        if field in plain and not _is_optional_string(plain[field]):
            field_type_errors.append(f"{field} must be a string or null.")
    for field in LIST_STRING_FIELDS:
        if field in plain and not _is_string_list(plain[field]):
            field_type_errors.append(f"{field} must be a list of strings.")

    for field in ("symptoms_status", "risk_flags_status"):
        if field in plain and plain[field] not in TRI_STATE_VALUES:
            field_type_errors.append(f"{field} has an invalid value.")

    turn_count = plain.get("turn_count")
    if "turn_count" in plain and (
        not isinstance(turn_count, int) or isinstance(turn_count, bool) or turn_count < 0
    ):
        field_type_errors.append("turn_count must be a non-negative integer.")
    if "metadata" in plain and not isinstance(plain["metadata"], dict):
        field_type_errors.append("metadata must be an object.")
    field_type_errors.extend(_validate_final_report_shape(plain.get("final_report")))

    try:
        RunState.model_validate(plain)
    except ValidationError as exc:
        field_type_errors.append(f"RunState schema validation failed: {exc.__class__.__name__}.")

    if field_type_errors:
        for error in field_type_errors:
            _fail(result, "field_type_invalid", error)
    else:
        result["checks"]["field_types"] = True

    state_version, used_fallback, version_error = _state_version_value(plain)
    if version_error:
        _fail(result, "state_version_invalid", version_error)
    else:
        result["checks"]["state_version"] = True
        if used_fallback:
            _warn(
                result,
                "state_version_missing_fallback",
                "state_version missing; using turn_count fallback for legacy state.",
            )
        if state_version is not None and isinstance(turn_count, int) and state_version < turn_count:
            _fail(
                result,
                "state_version_less_than_turn_count",
                "state_version must not be lower than turn_count.",
            )

    if contains_secret(plain):
        _fail(result, "secret_found", "state contains unredacted secret-like content.")
    else:
        result["checks"]["no_secret"] = True

    if _has_forbidden_medical_output(plain):
        _fail(result, "forbidden_medical_output", "state contains out-of-bound medical output.")
    else:
        result["checks"]["no_forbidden_medical_output"] = True

    result["passed"] = not result["errors"]
    return _redact_output(result)


def assert_state_valid(state: Any) -> None:
    result = validate_state(state)
    if not result["passed"]:
        raise ValueError(json.dumps(result["errors"], ensure_ascii=False, sort_keys=True))


def validate_state_json(state_json: str) -> dict[str, Any]:
    try:
        state = json.loads(state_json)
    except (json.JSONDecodeError, TypeError) as exc:
        result = _base_result()
        _fail(result, "state_json_corrupted", f"state_json could not be parsed: {type(exc).__name__}.")
        return result
    return validate_state(state)


def _fetch_session_payload_from_db(db_path: Path, session_id: str) -> dict[str, Any]:
    initialize_database(db_path)
    with connect(db_path) as conn:
        return _fetch_session_payload_from_conn(conn, session_id)


def _fetch_session_payload_from_conn(conn: sqlite3.Connection, session_id: str) -> dict[str, Any]:
    session_row = conn.execute(
        """
        SELECT session_id, created_at, updated_at, stage, mode, rag_enabled
        FROM sessions
        WHERE session_id = ?
        """,
        (session_id,),
    ).fetchone()
    state_row = conn.execute(
        "SELECT state_json, updated_at FROM session_states WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    turn_rows = conn.execute(
        """
        SELECT id, turn_index, user_input, response_json, created_at
        FROM turns
        WHERE session_id = ?
        ORDER BY turn_index ASC
        """,
        (session_id,),
    ).fetchall()
    report_rows = conn.execute(
        """
        SELECT report_id, state_version, created_at
        FROM reports
        WHERE session_id = ?
        ORDER BY created_at ASC, report_id ASC
        """,
        (session_id,),
    ).fetchall()
    return {
        "session": dict(session_row) if session_row is not None else None,
        "state_json": state_row["state_json"] if state_row is not None else None,
        "state_updated_at": state_row["updated_at"] if state_row is not None else None,
        "turns": [dict(row) for row in turn_rows],
        "reports": [dict(row) for row in report_rows],
    }


def _payload_from_store(store: Any, session_id: str) -> dict[str, Any]:
    if isinstance(store, (str, Path)):
        return _fetch_session_payload_from_db(Path(store), session_id)
    if isinstance(store, sqlite3.Connection):
        return _fetch_session_payload_from_conn(store, session_id)
    if isinstance(store, dict):
        if "state_json" in store:
            return store
        state = store.get("state")
        return {
            "session": store.get("session"),
            "state_json": json.dumps(state, ensure_ascii=False, sort_keys=True)
            if state is not None
            else None,
            "turns": list(store.get("turns") or []),
            "reports": list(store.get("reports") or []),
        }
    raise TypeError("store must be a db path, sqlite connection, or session payload dict.")


def _report_state_versions(reports: list[dict[str, Any]]) -> list[int]:
    versions: list[int] = []
    for row in reports:
        raw = row.get("state_version")
        if isinstance(raw, int) and not isinstance(raw, bool):
            versions.append(raw)
    return versions


def validate_session_consistency(store: Any, session_id: str) -> dict[str, Any]:
    result = {
        "passed": True,
        "errors": [],
        "warnings": [],
        "checks": {
            "session_exists": False,
            "state_exists": False,
            "state_valid": False,
            "turn_count_consistent": False,
            "state_version_consistent": False,
            "state_version_monotonic": False,
            "report_versions_consistent": False,
        },
        "session_id": redact_secret_text(str(session_id)),
        "turn_count": 0,
        "state_version": None,
        "report_count": 0,
        "state_validation": _base_result(),
    }

    try:
        payload = _payload_from_store(store, session_id)
    except Exception as exc:
        _fail(result, "store_unavailable", f"session store could not be read: {type(exc).__name__}.")
        return _redact_output(result)

    session = payload.get("session")
    if not session:
        _fail(result, "session_not_found", "session not found.")
        return _redact_output(result)
    result["checks"]["session_exists"] = True

    state_json = payload.get("state_json")
    if state_json is None:
        _fail(result, "state_not_found", "session state not found.")
        return _redact_output(result)
    result["checks"]["state_exists"] = True

    state_validation = validate_state_json(str(state_json))
    result["state_validation"] = state_validation
    if state_validation["passed"]:
        result["checks"]["state_valid"] = True
    else:
        _fail(result, "state_invalid", "state validator failed.")

    state: dict[str, Any] = {}
    try:
        loaded_state = json.loads(str(state_json))
        if isinstance(loaded_state, dict):
            state = loaded_state
    except json.JSONDecodeError:
        _fail(result, "state_json_corrupted", "state_json could not be parsed.")
        result["passed"] = False
        return _redact_output(result)

    turns = list(payload.get("turns") or [])
    reports = list(payload.get("reports") or [])
    db_turn_count = len(turns)
    result["turn_count"] = db_turn_count
    result["report_count"] = len(reports)

    state_turn_count = state.get("turn_count")
    if isinstance(state_turn_count, int) and not isinstance(state_turn_count, bool):
        if state_turn_count == db_turn_count:
            result["checks"]["turn_count_consistent"] = True
        else:
            _fail(
                result,
                "turn_count_mismatch",
                f"state turn_count {state_turn_count} does not match persisted turns {db_turn_count}.",
            )
    else:
        _fail(result, "turn_count_missing", "state turn_count is missing or invalid.")

    state_version, used_fallback, version_error = _state_version_value(state)
    result["state_version"] = state_version
    if version_error:
        _fail(result, "state_version_invalid", version_error)
    elif state_version is not None:
        if used_fallback:
            _warn(
                result,
                "state_version_missing_fallback",
                "state_version missing; using turn_count fallback for session consistency.",
            )
        if state_version >= db_turn_count:
            result["checks"]["state_version_consistent"] = True
        else:
            _fail(
                result,
                "state_version_lower_than_turns",
                f"state_version {state_version} is lower than persisted turns {db_turn_count}.",
            )

    turn_indexes = [row.get("turn_index") for row in turns]
    expected_indexes = list(range(1, db_turn_count + 1))
    if turn_indexes == expected_indexes:
        result["checks"]["state_version_monotonic"] = True
    else:
        _fail(
            result,
            "turn_indexes_not_monotonic",
            f"turn indexes are not monotonic: {turn_indexes}.",
        )

    report_versions = _report_state_versions(reports)
    if len(report_versions) != len(reports):
        _fail(result, "report_state_version_invalid", "one or more report state_version values are invalid.")
    elif report_versions != sorted(report_versions):
        _fail(result, "report_state_version_not_monotonic", "report state_version values are not monotonic.")
    elif state_version is not None and report_versions and max(report_versions) > state_version:
        _fail(
            result,
            "report_state_version_ahead",
            "latest report state_version is ahead of current state_version.",
        )
    else:
        result["checks"]["report_versions_consistent"] = True

    result["warnings"].extend(state_validation.get("warnings", []))
    result["passed"] = not result["errors"]
    return _redact_output(result)
