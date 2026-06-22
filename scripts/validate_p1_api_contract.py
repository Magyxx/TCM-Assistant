from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


COMPLETE_FAKE_INPUT = (
    "胃胀两天，没有其他症状，也没有胸痛"
)

SYNTHETIC_SECRET_VALUE = "sk-" + "contractsecret1234567890"
SECRET_PROBE_INPUT = (
    "胃胀两天"
    f" OPENAI_API_KEY={SYNTHETIC_SECRET_VALUE}"
)

EXPECTED_HEALTH = {
    "status": "ok",
    "service": "TCM-Assistant",
    "stage": "P1.1",
    "mode": "agentic_workflow",
    "diagnosis_system": False,
}

EXPECTED_CREATE_KEYS = {"session_id", "extractor_mode", "rag_enabled", "created_at", "turn_count"}
EXPECTED_TURN_KEYS = {
    "session_id",
    "turn_id",
    "turn_count",
    "next_question",
    "state",
    "risk_flags_status",
    "risk_rule_ids",
    "risk_reasons",
    "final_report",
    "metadata",
    "safety_disclaimer",
}
EXPECTED_STATE_KEYS = {
    "session_id",
    "turn_count",
    "state",
    "risk_flags_status",
    "risk_rule_ids",
    "missing_core_fields",
    "next_question",
    "metadata",
    "safety_disclaimer",
}
EXPECTED_REPORT_KEYS = {
    "session_id",
    "ready",
    "final_report",
    "missing_core_fields",
    "next_question",
    "safety_disclaimer",
}

FORBIDDEN_OUTPUT_TERMS = (
    "OPENAI_API_KEY",
    SYNTHETIC_SECRET_VALUE,
    ".env",
    "prescription",
    "treatment_plan",
    "treatment plan",
)


def _check(name: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _safe_keys(value: dict[str, Any]) -> list[str]:
    return sorted(str(key) for key in value.keys())


def _sidecar_bytes(db_path: Path) -> bytes:
    candidates = [
        db_path,
        db_path.with_name(f"{db_path.name}-wal"),
        db_path.with_name(f"{db_path.name}-shm"),
    ]
    payload = b""
    for path in candidates:
        if path.exists():
            payload += path.read_bytes()
    return payload


def _json_contains_forbidden(*payloads: dict[str, Any]) -> list[str]:
    text = json.dumps(payloads, ensure_ascii=False).lower()
    return [term for term in FORBIDDEN_OUTPUT_TERMS if term.lower() in text]


def run_contract_gate(db_path: Path) -> dict[str, Any]:
    os.environ["TCM_API_DB_PATH"] = str(db_path)

    from fastapi.testclient import TestClient

    from app.api.main import app
    from app.api.session_runtime import clear_session_cache, clear_sessions
    from app.api.sqlite_store import fetch_schema_meta, fetch_table_counts

    clear_sessions()
    client = TestClient(app)
    checks: list[dict[str, Any]] = []

    health_response = client.get("/health")
    health = health_response.json()
    checks.append(
        _check(
            "health_contract",
            health_response.status_code == 200 and health == EXPECTED_HEALTH,
            f"keys={_safe_keys(health)} stage={health.get('stage')!r}",
        )
    )

    session_response = client.post(
        "/sessions",
        json={"extractor_mode": "fake", "rag_enabled": True},
    )
    session = session_response.json()
    session_id = session.get("session_id", "")
    checks.append(
        _check(
            "create_session_contract",
            session_response.status_code == 200
            and set(session.keys()) == EXPECTED_CREATE_KEYS
            and session.get("extractor_mode") == "fake"
            and session.get("rag_enabled") is True
            and session.get("turn_count") == 0
            and bool(session_id),
            f"keys={_safe_keys(session)}",
        )
    )

    turn_response = client.post(
        f"/sessions/{session_id}/turn",
        json={"user_input": COMPLETE_FAKE_INPUT},
    )
    turn = turn_response.json()
    turn_metadata = turn.get("metadata") or {}
    checks.append(
        _check(
            "submit_turn_contract",
            turn_response.status_code == 200
            and set(turn.keys()) == EXPECTED_TURN_KEYS
            and turn.get("turn_count") == 1
            and turn_metadata.get("graph_runtime") == "langgraph"
            and turn_metadata.get("extractor_mode") == "fake"
            and "safety_disclaimer" in turn,
            f"keys={_safe_keys(turn)}",
        )
    )

    clear_session_cache()
    state_response = client.get(f"/sessions/{session_id}/state")
    state = state_response.json()
    checks.append(
        _check(
            "state_recovery_contract",
            state_response.status_code == 200
            and set(state.keys()) == EXPECTED_STATE_KEYS
            and state.get("turn_count") == 1
            and (state.get("state") or {}).get("turn_count") == 1,
            f"keys={_safe_keys(state)} turn_count={state.get('turn_count')!r}",
        )
    )

    report_response = client.get(f"/sessions/{session_id}/report")
    report = report_response.json()
    checks.append(
        _check(
            "report_recovery_contract",
            report_response.status_code == 200
            and set(report.keys()) == EXPECTED_REPORT_KEYS
            and isinstance(report.get("ready"), bool)
            and (
                isinstance(report.get("final_report"), dict)
                if report.get("ready")
                else report.get("final_report") is None
            )
            and isinstance(report.get("missing_core_fields"), list),
            f"keys={_safe_keys(report)} ready={report.get('ready')!r}",
        )
    )

    missing_turn_response = client.post(
        "/sessions/not-found/turn",
        json={"user_input": "胃胀两天"},
    )
    missing_state_response = client.get("/sessions/not-found/state")
    missing_report_response = client.get("/sessions/not-found/report")
    checks.append(
        _check(
            "missing_session_contract",
            missing_turn_response.status_code == 404
            and missing_state_response.status_code == 404
            and missing_report_response.status_code == 404,
            "turn/state/report missing-session responses checked",
        )
    )

    secret_session_response = client.post(
        "/sessions",
        json={"extractor_mode": "fake", "rag_enabled": True},
    )
    secret_session = secret_session_response.json()
    secret_turn_response = client.post(
        f"/sessions/{secret_session.get('session_id', '')}/turn",
        json={"user_input": SECRET_PROBE_INPUT},
    )
    secret_turn = secret_turn_response.json()

    forbidden_terms = _json_contains_forbidden(
        health,
        session,
        turn,
        state,
        report,
        secret_session,
        secret_turn,
    )
    checks.append(
        _check(
            "response_redaction_contract",
            secret_session_response.status_code == 200
            and secret_turn_response.status_code == 200
            and not forbidden_terms
            and health.get("diagnosis_system") is False,
            f"forbidden_terms={forbidden_terms}",
        )
    )

    schema_meta = fetch_schema_meta(db_path)
    table_counts = fetch_table_counts(db_path)
    checks.append(
        _check(
            "sqlite_schema_meta_contract",
            schema_meta.get("schema_stage") == "P1.3"
            and schema_meta.get("schema_version") == "1"
            and table_counts == {"sessions": 2, "session_states": 2, "turns": 2},
            f"schema_stage={schema_meta.get('schema_stage')!r} counts={table_counts}",
        )
    )

    persisted = _sidecar_bytes(db_path).decode("utf-8", errors="ignore")
    forbidden_persisted = [
        term
        for term in ("OPENAI_API_KEY", SYNTHETIC_SECRET_VALUE)
        if term in persisted
    ]
    checks.append(
        _check(
            "sqlite_redaction_contract",
            not forbidden_persisted,
            f"forbidden_persisted={forbidden_persisted}",
        )
    )

    passed = all(check["ok"] for check in checks)
    return {
        "stage": "P1.4",
        "feature": "API contract gate",
        "passed": passed,
        "db_path": str(db_path),
        "summary": {
            "health_stage": health.get("stage"),
            "diagnosis_system": health.get("diagnosis_system"),
            "session_created": bool(session_id),
            "turn_count_after_restart": state.get("turn_count"),
            "final_report_ready_after_restart": report.get("ready"),
            "schema_meta": schema_meta,
            "table_counts": table_counts,
        },
        "checks": checks,
        "boundaries": {
            "orm": False,
            "memory_manager": False,
            "embedding": False,
            "tool_registry": False,
            "multi_agent": False,
            "web_ui": False,
            "auth_or_users": False,
            "diagnosis_prescription_or_treatment_plan": False,
        },
    }


def _emit(result: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return

    print(f"stage: {result['stage']}")
    print(f"passed: {result['passed']}")
    for check in result["checks"]:
        status = "ok" if check["ok"] else "failed"
        print(f"{status}: {check['name']} - {check['detail']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the P1 API contract gate.")
    parser.add_argument(
        "--db",
        help="SQLite database path for the gate run. Requires --allow-clear.",
    )
    parser.add_argument(
        "--allow-clear",
        action="store_true",
        help="Allow the gate to clear sessions in the selected SQLite DB.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args()

    if args.db and not args.allow_clear:
        parser.error("--db requires --allow-clear because this gate resets API sessions")

    previous_db_path = os.environ.get("TCM_API_DB_PATH")
    try:
        if args.db:
            result = run_contract_gate(Path(args.db))
            _emit(result, json_output=args.json)
            raise SystemExit(0 if result["passed"] else 1)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_contract_gate(Path(temp_dir) / "p1_4_contract.sqlite3")
            _emit(result, json_output=args.json)
            raise SystemExit(0 if result["passed"] else 1)
    finally:
        if previous_db_path is None:
            os.environ.pop("TCM_API_DB_PATH", None)
        else:
            os.environ["TCM_API_DB_PATH"] = previous_db_path


if __name__ == "__main__":
    main()
