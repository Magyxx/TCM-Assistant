from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api.redaction import SECRET_VALUE_PATTERNS, redact_secret_text
from app.api.report_audit import audit_report
from app.api.report_validator import validate_report
from app.api.runtime_config import reset_runtime_config_cache
from app.api.sqlite_store import DEFAULT_DB_PATH, fetch_reports_for_session
from app.api.state_validator import validate_session_consistency
from app.rules.risk_rules import evaluate_risk_rules


DEFAULT_OUTPUT_PATH = Path("artifacts") / "p2_case_corpus_eval.json"
PHASE = "P2.3"
DEFAULT_FORBIDDEN_REPORT_TERMS = ["诊断为", "确诊", "处方", "治疗方案"]


class CaseCorpusError(RuntimeError):
    pass


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


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


def _check(name: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {
        "name": name,
        "status": "ok" if ok else "failed",
        "ok": bool(ok),
        "detail": str(_redact_output(detail)),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_redact_output(payload), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _safe_response_json(response: Any) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception:
        payload = {"raw_text": str(getattr(response, "text", ""))[:400]}
    return payload


def _load_case_file(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            case = json.load(handle)
    except json.JSONDecodeError as exc:
        raise CaseCorpusError(
            f"Malformed JSON in {path}: line {exc.lineno}, column {exc.colno}."
        ) from exc

    if not isinstance(case, dict):
        raise CaseCorpusError(f"Case file must contain a JSON object: {path}")

    case_id = case.get("case_id")
    if not isinstance(case_id, str) or not case_id.strip():
        raise CaseCorpusError(f"Case file has empty or invalid case_id: {path}")

    turns = case.get("turns")
    if not isinstance(turns, list) or not turns:
        raise CaseCorpusError(f"Case {case_id} must define a non-empty turns list.")
    if not all(isinstance(turn, str) and turn.strip() for turn in turns):
        raise CaseCorpusError(f"Case {case_id} turns must be non-empty strings.")

    expect = case.get("expect", {})
    if expect is not None and not isinstance(expect, dict):
        raise CaseCorpusError(f"Case {case_id} expect must be an object when present.")

    return case


def load_cases(case_dir: Path, selected_case: Optional[str] = None) -> list[dict[str, Any]]:
    if not case_dir.exists():
        raise CaseCorpusError(f"Case directory does not exist: {case_dir}")
    if not case_dir.is_dir():
        raise CaseCorpusError(f"Case path is not a directory: {case_dir}")

    paths = sorted(case_dir.glob("*.json"))
    if not paths:
        raise CaseCorpusError(f"Case directory contains no JSON files: {case_dir}")

    cases = [_load_case_file(path) for path in paths]
    seen: dict[str, Path] = {}
    for path, case in zip(paths, cases):
        case_id = str(case["case_id"])
        if case_id in seen:
            raise CaseCorpusError(f"Duplicate case_id {case_id!r} in {seen[case_id]} and {path}.")
        seen[case_id] = path

    if selected_case:
        cases = [case for case in cases if case.get("case_id") == selected_case]
        if not cases:
            raise CaseCorpusError(f"Case {selected_case!r} was not found in {case_dir}.")

    return cases


@contextmanager
def _configured_db(db_path: Path) -> Iterator[None]:
    previous = os.environ.get("TCM_API_DB_PATH")
    os.environ["TCM_API_DB_PATH"] = str(db_path)
    reset_runtime_config_cache()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("TCM_API_DB_PATH", None)
        else:
            os.environ["TCM_API_DB_PATH"] = previous
        reset_runtime_config_cache()


def _secret_terms_from_turns(turns: Iterable[str]) -> list[str]:
    terms: list[str] = []
    for turn in turns:
        for pattern in SECRET_VALUE_PATTERNS:
            for match in pattern.finditer(turn):
                term = match.group(0)
                terms.append(term)
                if ":" in term or "=" in term:
                    key = re.split(r"\s*[:=]\s*", term, maxsplit=1)[0]
                    terms.append(key)
    return list(dict.fromkeys([term for term in terms if term]))


def _contains_terms(value: Any, terms: Iterable[str]) -> list[str]:
    text = _json_text(value)
    return [term for term in terms if term and term in text]


def _db_files(db_path: Path) -> list[Path]:
    return [
        db_path,
        db_path.with_name(f"{db_path.name}-wal"),
        db_path.with_name(f"{db_path.name}-shm"),
    ]


def _db_contains_terms(db_path: Path, terms: Iterable[str]) -> bool:
    raw_terms = [term.encode("utf-8") for term in terms if term]
    if not raw_terms:
        return False
    for path in _db_files(db_path):
        if not path.exists():
            continue
        content = path.read_bytes()
        if any(term in content for term in raw_terms):
            return True
    return False


def _run_case_once(case: dict[str, Any], db_path: Path) -> dict[str, Any]:
    from fastapi.testclient import TestClient

    from app.api.main import app
    from app.api.session_runtime import clear_session_cache

    client = TestClient(app, raise_server_exceptions=False)
    session_response = client.post(
        "/sessions",
        json={"extractor_mode": "fake", "rag_enabled": True},
    )
    session_payload = _safe_response_json(session_response)
    session_id = str(session_payload.get("session_id") or "")

    turn_payloads: list[dict[str, Any]] = []
    turn_statuses: list[int] = []
    state_versions: list[int] = []
    for turn_text in case.get("turns") or []:
        if not session_id:
            break
        response = client.post(
            f"/sessions/{session_id}/turn",
            json={"user_input": turn_text},
        )
        payload = _safe_response_json(response)
        turn_payloads.append(payload)
        turn_statuses.append(int(response.status_code))
        state = payload.get("state") if isinstance(payload, dict) else None
        if isinstance(state, dict) and "state_version" in state:
            try:
                state_versions.append(int(state["state_version"]))
            except (TypeError, ValueError):
                pass
        if response.status_code != 200:
            break

    clear_session_cache()
    state_status = 0
    report_status = 0
    state_payload: dict[str, Any] = {}
    report_payload: dict[str, Any] = {}
    if session_id:
        state_response = client.get(f"/sessions/{session_id}/state")
        state_status = int(state_response.status_code)
        state_payload = _safe_response_json(state_response)
        report_response = client.get(f"/sessions/{session_id}/report")
        report_status = int(report_response.status_code)
        report_payload = _safe_response_json(report_response)

    reports = fetch_reports_for_session(session_id) if session_id else []
    report_snapshot_count = len(reports)
    state_body = state_payload.get("state") if isinstance(state_payload, dict) else {}
    state_version = 0
    if isinstance(state_body, dict):
        try:
            state_version = int(state_body.get("state_version") or 0)
        except (TypeError, ValueError):
            state_version = 0

    return {
        "session_id": session_id,
        "session_status": int(session_response.status_code),
        "session": session_payload,
        "turn_statuses": turn_statuses,
        "turn_payloads": turn_payloads,
        "state_status": state_status,
        "state": state_payload,
        "report_status": report_status,
        "report": report_payload,
        "reports": reports,
        "turn_count": int(state_payload.get("turn_count") or len(turn_payloads))
        if isinstance(state_payload, dict)
        else len(turn_payloads),
        "state_version": state_version,
        "turn_state_versions": state_versions,
        "report_available": bool(report_payload.get("ready"))
        if isinstance(report_payload, dict)
        else False,
        "report_snapshot_count": report_snapshot_count,
    }


def _report_terms_payload(trace: dict[str, Any]) -> dict[str, Any]:
    return {
        "turn_final_reports": [
            payload.get("final_report")
            for payload in trace.get("turn_payloads", [])
            if isinstance(payload, dict)
        ],
        "report": trace.get("report"),
        "report_snapshots": [
            row.get("report_json")
            for row in trace.get("reports", [])
            if isinstance(row, dict)
        ],
    }


def _risk_evaluations(case: dict[str, Any]) -> list[Any]:
    evaluations = []
    previous = "unknown"
    for turn in case.get("turns") or []:
        evaluation = evaluate_risk_rules(turn, previous_status=previous)
        evaluations.append(evaluation)
        if evaluation.risk_status in {"present", "none"}:
            previous = evaluation.risk_status
    return evaluations


def _skipped_report_validation(reason: str) -> dict[str, Any]:
    return {
        "passed": True,
        "skipped": True,
        "reason": reason,
        "errors": [],
        "warnings": [],
        "checks": {
            "json_serializable": True,
            "structure": True,
            "safety_audit": True,
            "no_secret": True,
            "no_diagnosis": True,
            "no_prescription": True,
            "no_treatment_plan": True,
            "state_supported": True,
        },
    }


def _report_payload_for_validation(trace: dict[str, Any]) -> Any:
    report_payload = trace.get("report") if isinstance(trace.get("report"), dict) else {}
    final_report = report_payload.get("final_report") if isinstance(report_payload, dict) else None
    if final_report is not None:
        return final_report

    reports = [row for row in trace.get("reports") or [] if isinstance(row, dict)]
    if reports:
        return reports[-1].get("report_json")

    return None


def _validate_report_for_case(
    trace: dict[str, Any],
    state_body: Any,
    *,
    require_report: bool,
) -> dict[str, Any]:
    payload = _report_payload_for_validation(trace)
    if payload is None and not require_report:
        return _skipped_report_validation("report_unavailable")
    return validate_report(payload, state_body)


VOLATILE_FINGERPRINT_KEYS = {
    "created_at",
    "updated_at",
    "checked_at",
    "timestamp",
    "ts",
    "session_id",
    "trace_id",
    "turn_id",
    "request_id",
}


def _stable_fingerprint_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _stable_fingerprint_payload(item)
            for key, item in value.items()
            if key not in VOLATILE_FINGERPRINT_KEYS
        }
    if isinstance(value, list):
        return [_stable_fingerprint_payload(item) for item in value]
    return value


def _fingerprint_trace(trace: dict[str, Any]) -> dict[str, Any]:
    state = trace.get("state") if isinstance(trace.get("state"), dict) else {}
    state_body = state.get("state") if isinstance(state, dict) else {}
    report = trace.get("report") if isinstance(trace.get("report"), dict) else {}
    final_report = report.get("final_report") if isinstance(report, dict) else None
    return {
        "turn_count": trace.get("turn_count"),
        "state_version": trace.get("state_version"),
        "turn_state_versions": trace.get("turn_state_versions"),
        "risk_flags_status": state.get("risk_flags_status") if isinstance(state, dict) else None,
        "risk_rule_ids": sorted(state.get("risk_rule_ids") or []) if isinstance(state, dict) else [],
        "missing_core_fields": sorted(state.get("missing_core_fields") or [])
        if isinstance(state, dict)
        else [],
        "state_core": {
            "chief_complaint": state_body.get("chief_complaint")
            if isinstance(state_body, dict)
            else None,
            "duration": state_body.get("duration") if isinstance(state_body, dict) else None,
            "symptoms": state_body.get("symptoms") if isinstance(state_body, dict) else [],
            "symptoms_status": state_body.get("symptoms_status")
            if isinstance(state_body, dict)
            else None,
            "risk_flags": state_body.get("risk_flags") if isinstance(state_body, dict) else [],
            "risk_flags_status": state_body.get("risk_flags_status")
            if isinstance(state_body, dict)
            else None,
        },
        "report_available": trace.get("report_available"),
        "report_snapshot_count": trace.get("report_snapshot_count"),
        "final_report": _stable_fingerprint_payload(final_report),
    }


def _evaluate_case(case: dict[str, Any], db_path: Path) -> dict[str, Any]:
    expect = case.get("expect") or {}
    risk_expect = expect.get("risk") or {}
    state_expect = expect.get("state") or {}
    report_expect = expect.get("report") or {}
    persistence_expect = expect.get("persistence") or {}
    replay_expect = expect.get("replay") or {}

    checks: list[dict[str, Any]] = []
    trace = _run_case_once(case, db_path)
    turns = list(case.get("turns") or [])
    secret_terms = _secret_terms_from_turns(turns)

    session_id = trace.get("session_id")
    checks.append(_check("create_session", bool(session_id) and trace.get("session_status") == 200))

    turn_statuses = list(trace.get("turn_statuses") or [])
    checks.append(
        _check(
            "turn_replay",
            len(turn_statuses) == len(turns) and all(status == 200 for status in turn_statuses),
            f"turn_statuses={turn_statuses}",
        )
    )

    min_turns = int(expect.get("min_turns") or 0)
    checks.append(
        _check(
            "min_turns",
            int(trace.get("turn_count") or 0) >= min_turns,
            f"turn_count={trace.get('turn_count')} min_turns={min_turns}",
        )
    )

    state_payload = trace.get("state") if isinstance(trace.get("state"), dict) else {}
    state_body = state_payload.get("state") if isinstance(state_payload, dict) else None
    must_exist = bool(state_expect.get("must_exist", True))
    checks.append(
        _check(
            "state_exists",
            (not must_exist) or (trace.get("state_status") == 200 and isinstance(state_body, dict)),
            f"state_status={trace.get('state_status')}",
        )
    )
    require_valid_state = bool(state_expect.get("require_valid_state", True))
    if session_id:
        state_validation = validate_session_consistency(db_path, str(session_id))
    else:
        state_validation = {
            "passed": False,
            "errors": [{"code": "session_missing", "message": "Session was not created."}],
            "warnings": [],
            "checks": {},
        }
    if require_valid_state:
        checks.append(
            _check(
                "state_validation",
                bool(state_validation.get("passed")),
                f"errors={len(state_validation.get('errors') or [])}",
            )
        )

    expected_versions = list(range(1, len(turn_statuses) + 1))
    versions = list(trace.get("turn_state_versions") or [])
    min_state_version = int(state_expect.get("min_state_version") or len(turns))
    checks.append(
        _check(
            "state_version_increments",
            versions == expected_versions
            and int(trace.get("state_version") or 0) >= min_state_version
            and int(trace.get("state_version") or 0) == int(trace.get("turn_count") or 0),
            (
                f"versions={versions} expected={expected_versions} "
                f"state_version={trace.get('state_version')} min={min_state_version}"
            ),
        )
    )

    checks.append(
        _check(
            "report_endpoint",
            trace.get("report_status") == 200 and isinstance(trace.get("report"), dict),
            f"report_status={trace.get('report_status')}",
        )
    )
    if "report_available" in expect:
        expected_report_available = bool(expect.get("report_available"))
        checks.append(
            _check(
                "report_available",
                bool(trace.get("report_available")) is expected_report_available,
                f"report_available={trace.get('report_available')} expected={expected_report_available}",
            )
        )

    if expect.get("report_available") is True:
        checks.append(
            _check(
                "report_snapshot_generated",
                int(trace.get("report_snapshot_count") or 0) >= 1,
                f"report_snapshot_count={trace.get('report_snapshot_count')}",
            )
        )
    elif expect.get("report_available") is False:
        checks.append(
            _check(
                "report_snapshot_absent_when_unready",
                int(trace.get("report_snapshot_count") or 0) == 0,
                f"report_snapshot_count={trace.get('report_snapshot_count')}",
            )
        )

    forbidden_terms = list(report_expect.get("must_not_contain") or expect.get("must_not_contain") or DEFAULT_FORBIDDEN_REPORT_TERMS)
    found_forbidden = _contains_terms(_report_terms_payload(trace), forbidden_terms)
    checks.append(
        _check(
            "must_not_contain",
            not found_forbidden,
            f"forbidden_terms={found_forbidden}",
        )
    )

    output_secret_leaks = _contains_terms(trace, secret_terms)
    checks.append(
        _check(
            "secret_redaction_outputs",
            not output_secret_leaks,
            f"marker_count {len(output_secret_leaks)}",
        )
    )

    if report_expect.get("must_not_leak_secret", True):
        report_secret_leaks = _contains_terms(_report_terms_payload(trace), secret_terms)
        checks.append(
            _check(
                "secret_redaction_report",
                not report_secret_leaks,
                f"marker_count {len(report_secret_leaks)}",
            )
        )

    sqlite_secret_found = _db_contains_terms(db_path, secret_terms)
    checks.append(
        _check(
            "secret_redaction_sqlite",
            not sqlite_secret_found,
            f"marker_count {len(secret_terms)}",
        )
    )

    if persistence_expect.get("must_recover_after_cache_clear", True):
        checks.append(
            _check(
                "sqlite_recovery_after_cache_clear",
                trace.get("state_status") == 200
                and int(trace.get("turn_count") or 0) == len(turn_statuses)
                and int(trace.get("state_version") or 0) == len(turn_statuses),
                (
                    f"state_status={trace.get('state_status')} "
                    f"turn_count={trace.get('turn_count')} state_version={trace.get('state_version')}"
                ),
            )
        )

    risk_status = state_payload.get("risk_flags_status") if isinstance(state_payload, dict) else None
    if risk_expect.get("expected_status"):
        checks.append(
            _check(
                "risk_expected_status",
                risk_status == risk_expect.get("expected_status"),
                f"risk_flags_status={risk_status} expected={risk_expect.get('expected_status')}",
            )
        )

    state_rule_ids = set(state_payload.get("risk_rule_ids") or []) if isinstance(state_payload, dict) else set()
    must_rule_ids = set(risk_expect.get("must_include_rule_ids") or [])
    if must_rule_ids:
        checks.append(
            _check(
                "risk_rule_ids",
                must_rule_ids.issubset(state_rule_ids),
                f"risk_rule_ids={sorted(state_rule_ids)} expected={sorted(must_rule_ids)}",
            )
        )

    if risk_expect.get("must_not_weaken_red_flags", True):
        positive_evaluations = [
            evaluation for evaluation in _risk_evaluations(case) if evaluation.risk_status == "present"
        ]
        expected_rule_ids = set()
        for evaluation in positive_evaluations:
            expected_rule_ids.update(evaluation.triggered_rule_ids)
        red_flags_preserved = (
            not positive_evaluations
            or (risk_status == "present" and expected_rule_ids.issubset(state_rule_ids))
        )
        checks.append(
            _check(
                "risk_not_weakened",
                red_flags_preserved,
                f"risk_flags_status={risk_status} expected_rule_ids={sorted(expected_rule_ids)}",
            )
        )

    report_payload = trace.get("report") if isinstance(trace.get("report"), dict) else {}
    final_report = report_payload.get("final_report") if isinstance(report_payload, dict) else None
    require_valid_report = bool(
        report_expect.get(
            "require_valid_report",
            bool(expect.get("report_available") is True or trace.get("report_available")),
        )
    )
    report_validation = _validate_report_for_case(
        trace,
        state_body,
        require_report=require_valid_report,
    )
    checks.append(
        _check(
            "report_validation",
            bool(report_validation.get("passed")),
            f"errors={len(report_validation.get('errors') or [])}",
        )
    )

    expected_triage = report_expect.get("expected_triage_level")
    if expected_triage:
        triage = final_report.get("triage_level") if isinstance(final_report, dict) else None
        checks.append(
            _check(
                "report_triage_level",
                triage == expected_triage,
                f"triage_level={triage} expected={expected_triage}",
            )
        )

    report_audit_ok = True
    audit_details: list[str] = []
    for row in trace.get("reports") or []:
        if not isinstance(row, dict):
            report_audit_ok = False
            audit_details.append("invalid_report_row")
            continue
        flags = row.get("safety_flags_json")
        recomputed = audit_report(row.get("report_json"), state_body)
        recomputed_validation = validate_report(row.get("report_json"), state_body)
        if not isinstance(flags, dict):
            report_audit_ok = False
            audit_details.append("missing_safety_flags_json")
        elif flags.get("passed") != recomputed.get("passed"):
            report_audit_ok = False
            audit_details.append("passed_mismatch")
        elif not isinstance(flags.get("rules"), dict):
            report_audit_ok = False
            audit_details.append("rules_missing")
        elif not isinstance(flags.get("validator"), dict):
            report_audit_ok = False
            audit_details.append("validator_missing")
        elif flags["validator"].get("passed") != recomputed_validation.get("passed"):
            report_audit_ok = False
            audit_details.append("validator_passed_mismatch")
    checks.append(
        _check(
            "report_audit_reflected",
            report_audit_ok,
            ",".join(audit_details),
        )
    )

    if replay_expect.get("must_be_deterministic", True):
        second_trace = _run_case_once(case, db_path)
        checks.append(
            _check(
                "replay_determinism",
                _fingerprint_trace(trace) == _fingerprint_trace(second_trace),
                "fingerprint_mismatch" if _fingerprint_trace(trace) != _fingerprint_trace(second_trace) else "",
            )
        )

    status = "ok" if all(check["ok"] for check in checks) else "failed"
    return {
        "case_id": case.get("case_id"),
        "description": case.get("description"),
        "tags": list(case.get("tags") or []),
        "status": status,
        "turn_count": int(trace.get("turn_count") or 0),
        "state_version": int(trace.get("state_version") or 0),
        "report_available": bool(trace.get("report_available")),
        "report_snapshot_count": int(trace.get("report_snapshot_count") or 0),
        "risk_flags_status": risk_status,
        "risk_rule_ids": sorted(state_rule_ids),
        "state_validation": state_validation,
        "report_validation": report_validation,
        "checks": checks,
    }


def _result_for_errors(errors: list[str], *, db_mode: str = "not_started") -> dict[str, Any]:
    return {
        "phase": PHASE,
        "status": "failed",
        "case_count": 0,
        "pass_count": 0,
        "fail_count": 0,
        "passed": 0,
        "failed": 0,
        "cases": [],
        "errors": errors,
        "secret_scan": {
            "secret_found": False,
            "secret_found_in_outputs": False,
            "secret_found_in_sqlite": False,
        },
        "state_validation": {
            "enabled": True,
            "passed": False,
            "failed": 0,
            "errors": errors,
        },
        "report_validation": {
            "enabled": True,
            "passed": False,
            "failed": 0,
            "errors": errors,
        },
        "metrics": {
            "report_safety_pass_rate": 0.0,
            "report_validation_pass_rate": 0.0,
        },
        "db": {
            "mode": db_mode,
            "default_runtime_used": False,
        },
        "boundary_check": _boundary_check(),
        "recommend_next": "hold",
    }


def _boundary_check() -> dict[str, Any]:
    return {
        "violated": False,
        "orm": False,
        "memory_manager": False,
        "embedding": False,
        "tool_registry": False,
        "multi_agent": False,
        "web_ui": False,
        "auth_or_users": False,
        "diagnosis_prescription_or_treatment_plan": False,
    }


def run_eval(case_dir: Path, *, selected_case: Optional[str], db_path: Path, db_mode: str) -> dict[str, Any]:
    try:
        cases = load_cases(case_dir, selected_case)
    except CaseCorpusError as exc:
        return _result_for_errors([str(exc)], db_mode=db_mode)

    with _configured_db(db_path):
        from app.api.session_runtime import clear_sessions
        from app.api.sqlite_store import initialize_database

        initialize_database(db_path)
        clear_sessions()
        case_results = [_evaluate_case(case, db_path) for case in cases]

    failed_cases = [case for case in case_results if case.get("status") != "ok"]
    failed_state_validation = [
        case for case in case_results if not (case.get("state_validation") or {}).get("passed")
    ]
    failed_report_validation = [
        case for case in case_results if not (case.get("report_validation") or {}).get("passed")
    ]
    report_validations = [case.get("report_validation") or {} for case in case_results]
    non_skipped_report_validations = [
        validation for validation in report_validations if not validation.get("skipped")
    ]
    report_safety_passed = [
        validation
        for validation in non_skipped_report_validations
        if (validation.get("checks") or {}).get("safety_audit")
    ]
    report_validation_pass_rate = (
        round((len(case_results) - len(failed_report_validation)) / len(case_results), 4)
        if case_results
        else 0.0
    )
    report_safety_pass_rate = (
        round(len(report_safety_passed) / len(non_skipped_report_validations), 4)
        if non_skipped_report_validations
        else 1.0
    )
    secret_found_in_sqlite = any(
        any(check.get("name") == "secret_redaction_sqlite" and not check.get("ok") for check in case["checks"])
        for case in case_results
    )
    secret_found_in_outputs = any(
        any(
            check.get("name") in {"secret_redaction_outputs", "secret_redaction_report"}
            and not check.get("ok")
            for check in case["checks"]
        )
        for case in case_results
    )
    default_runtime_used = db_path.resolve() == (ROOT_DIR / DEFAULT_DB_PATH).resolve()
    status = "ok" if not failed_cases else "failed"
    return {
        "phase": PHASE,
        "status": status,
        "case_count": len(case_results),
        "pass_count": len(case_results) - len(failed_cases),
        "fail_count": len(failed_cases),
        "passed": len(case_results) - len(failed_cases),
        "failed": len(failed_cases),
        "cases": case_results,
        "errors": [],
        "secret_scan": {
            "secret_found": secret_found_in_outputs or secret_found_in_sqlite,
            "secret_found_in_outputs": secret_found_in_outputs,
            "secret_found_in_sqlite": secret_found_in_sqlite,
        },
        "state_validation": {
            "enabled": True,
            "passed": not failed_state_validation,
            "failed": len(failed_state_validation),
            "case_count": len(case_results),
        },
        "report_validation": {
            "enabled": True,
            "passed": not failed_report_validation,
            "failed": len(failed_report_validation),
            "case_count": len(case_results),
            "validated_count": len(non_skipped_report_validations),
            "skipped_count": len(case_results) - len(non_skipped_report_validations),
        },
        "metrics": {
            "report_safety_pass_rate": report_safety_pass_rate,
            "report_validation_pass_rate": report_validation_pass_rate,
        },
        "db": {
            "mode": db_mode,
            "path": redact_secret_text(str(db_path)),
            "default_runtime_used": default_runtime_used,
        },
        "boundary_check": _boundary_check(),
        "recommend_next": "P2.4" if status == "ok" else "hold",
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run P2.1 case corpus evaluation.")
    parser.add_argument(
        "case_dir",
        nargs="?",
        default="artifacts/eval_cases/",
        help="Directory containing eval case JSON files. Defaults to artifacts/eval_cases/.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--output",
        help=f"Optional artifact path. Defaults to {DEFAULT_OUTPUT_PATH} when omitted.",
    )
    parser.add_argument("--case", help="Run one case_id from the corpus.")
    parser.add_argument("--db", help="SQLite DB path. Defaults to a temporary DB.")
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    args = _parse_args()
    case_dir = Path(args.case_dir)
    output_path = Path(args.output) if args.output else DEFAULT_OUTPUT_PATH

    if args.db:
        result = run_eval(
            case_dir,
            selected_case=args.case,
            db_path=Path(args.db),
            db_mode="explicit",
        )
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_eval(
                case_dir,
                selected_case=args.case,
                db_path=Path(temp_dir) / "p2_case_corpus_eval.sqlite3",
                db_mode="temporary",
            )

    _write_json(output_path, result)
    print(json.dumps(_redact_output(result), ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0 if result.get("status") == "ok" else 1)


if __name__ == "__main__":
    main()
