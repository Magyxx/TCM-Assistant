from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

STAGE = "P12-M2_API_CONTRACT"
DEFAULT_OUTPUT = ROOT_DIR / "artifacts" / "p12" / "api_contract.json"

SAFE_COMPLETE_INPUT = "胃胀一周，没有其他症状，睡眠一般，食欲一般，大便正常，小便正常，没有胸痛，没有呼吸困难，没有便血"
HIGH_RISK_INPUT = "胸痛伴呼吸困难半天"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


@contextmanager
def _temporary_api_client() -> Iterator[tuple[Any, dict[str, Path]]]:
    from fastapi.testclient import TestClient

    with tempfile.TemporaryDirectory(prefix="p12-api-", ignore_cleanup_errors=True) as temp:
        temp_root = Path(temp)
        paths = {
            "session_db": temp_root / "p12_sessions.sqlite3",
            "api_log": temp_root / "api_events.jsonl",
            "legacy_db": temp_root / "api.sqlite3",
            "p7_db": temp_root / "p7.sqlite3",
        }
        env = {
            "EXTRACTOR_BACKEND": "fake",
            "ENABLE_REAL_LLM": "false",
            "TCM_ALLOW_REAL_LLM": "false",
            "RUN_LOCAL_VLLM_SMOKE": "0",
            "SESSION_STORE_BACKEND": "sqlite",
            "SESSION_SQLITE_PATH": str(paths["session_db"]),
            "API_LOG_PATH": str(paths["api_log"]),
            "TCM_API_DB_PATH": str(paths["legacy_db"]),
            "TCM_SQLITE_PATH": str(paths["p7_db"]),
        }
        previous = {name: os.environ.get(name) for name in env}
        os.environ.update(env)
        from app.api.deps import set_consultation_service_override
        from app.api.main import app
        from app.api.session_runtime import clear_sessions
        from app.services.consultation_service import ConsultationService

        clear_sessions()
        set_consultation_service_override(
            ConsultationService(sqlite_path=paths["session_db"], api_log_path=paths["api_log"])
        )
        client = TestClient(app, raise_server_exceptions=False)
        try:
            yield client, paths
        finally:
            client.close()
            clear_sessions()
            set_consultation_service_override(None)
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value


def _post_session(client: Any) -> dict[str, Any]:
    response = client.post(
        "/sessions",
        json={"backend": "fake", "rag_enabled": True, "metadata": {"p12": STAGE}},
    )
    return {
        "status_code": response.status_code,
        "payload": response.json() if response.content else {},
    }


def _post_turn(client: Any, session_id: str, user_input: str) -> dict[str, Any]:
    response = client.post(
        f"/sessions/{session_id}/turn",
        json={"user_input": user_input, "extractor_backend": "fake", "metadata": {"p12": STAGE}},
    )
    return {
        "status_code": response.status_code,
        "payload": response.json() if response.content else {},
    }


def _get_json(client: Any, path: str) -> dict[str, Any]:
    response = client.get(path)
    return {
        "status_code": response.status_code,
        "payload": response.json() if response.content else {},
    }


def _payload_without_disclaimer(payload: Any) -> Any:
    if isinstance(payload, list):
        return [_payload_without_disclaimer(item) for item in payload]
    if isinstance(payload, dict):
        return {
            key: _payload_without_disclaimer(value)
            for key, value in payload.items()
            if key != "safety_disclaimer"
        }
    return payload


def _sanitize_temp_paths(value: Any, temp_root: Path) -> Any:
    temp_root_text = str(temp_root)
    if isinstance(value, str):
        return value.replace(temp_root_text, "<tempdir>")
    if isinstance(value, list):
        return [_sanitize_temp_paths(item, temp_root) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_temp_paths(item, temp_root) for key, item in value.items()}
    return value


def _forbidden_medical_output_absent(payload: dict[str, Any]) -> bool:
    public_text = json.dumps(_payload_without_disclaimer(payload), ensure_ascii=False).lower()
    forbidden = [
        "诊断为",
        "确诊为",
        "prescribed",
        "take this prescription",
    ]
    return not any(term in public_text for term in forbidden)


def verify() -> dict[str, Any]:
    with _temporary_api_client() as (client, paths):
        health = _get_json(client, "/health?extended=true")
        session = _post_session(client)
        session_id = str(session["payload"].get("session_id") or "")
        turn = _post_turn(client, session_id, SAFE_COMPLETE_INPUT) if session_id else {"status_code": 0, "payload": {}}
        state = _get_json(client, f"/sessions/{session_id}/state") if session_id else {"status_code": 0, "payload": {}}

        high_risk_session = _post_session(client)
        high_risk_session_id = str(high_risk_session["payload"].get("session_id") or "")
        high_risk_turn = (
            _post_turn(client, high_risk_session_id, HIGH_RISK_INPUT)
            if high_risk_session_id
            else {"status_code": 0, "payload": {}}
        )

    temp_root = paths["legacy_db"].parent
    health_payload = _sanitize_temp_paths(health["payload"], temp_root)
    turn_payload = turn["payload"]
    state_payload = state["payload"]
    high_risk_payload = high_risk_turn["payload"]
    backend_summary = health_payload.get("backend_matrix_summary") or {}
    live_vllm = health_payload.get("live_vllm") or {}

    checks = {
        "health_returns_readiness": health["status_code"] == 200
        and health_payload.get("status") == "ok"
        and health_payload.get("storage_status", {}).get("default_backend") == "sqlite"
        and "backend_count" in backend_summary
        and live_vllm.get("status") == "skipped",
        "create_session_returns_contract": session["status_code"] == 200
        and bool(session_id)
        and session["payload"].get("extractor_mode") == "fake"
        and session["payload"].get("rag_enabled") is True,
        "turn_returns_contract": turn["status_code"] == 200
        and turn_payload.get("session_id") == session_id
        and bool(turn_payload.get("turn_id"))
        and int(turn_payload.get("turn_count") or 0) == 1
        and ("state_summary" in turn_payload or "next_question" in turn_payload),
        "state_reads_after_turn": state["status_code"] == 200
        and state_payload.get("session_id") == session_id
        and int(state_payload.get("turn_count") or 0) == 1,
        "risk_rules_fallback_high_risk": high_risk_turn["status_code"] == 200
        and high_risk_payload.get("risk_flags_status") == "present"
        and bool(high_risk_payload.get("risk_rule_ids")),
        "no_forbidden_medical_output": _forbidden_medical_output_absent(turn_payload)
        and _forbidden_medical_output_absent(high_risk_payload),
        "optional_backends_not_required": live_vllm.get("skip_reason") == "RUN_LOCAL_VLLM_SMOKE is not enabled",
        "temporary_test_db_used": all(str(path).startswith(str(paths["legacy_db"].parent)) for path in paths.values()),
    }
    status = "ok" if all(checks.values()) else "failed"
    return {
        "stage": STAGE,
        "status": status,
        "branch": _git(["branch", "--show-current"]),
        "head": _git(["rev-parse", "HEAD"]),
        "base_main": _git(["rev-parse", "origin/main"]),
        "api_routes": {
            "health": "GET /health",
            "sessions": "POST /sessions",
            "turn": "POST /sessions/{session_id}/turn",
            "state": "GET /sessions/{session_id}/state",
        },
        "health": {
            "status_code": health["status_code"],
            "storage_status": health_payload.get("storage_status"),
            "backend_matrix_summary": backend_summary,
            "live_vllm": live_vllm,
            "p11_contract_availability": health_payload.get("p11_contract_availability"),
        },
        "session_contract": {
            "status_code": session["status_code"],
            "session_id_present": bool(session_id),
            "extractor_mode": session["payload"].get("extractor_mode"),
            "rag_enabled": session["payload"].get("rag_enabled"),
        },
        "turn_contract": {
            "status_code": turn["status_code"],
            "session_id_matches": turn_payload.get("session_id") == session_id,
            "turn_id_present": bool(turn_payload.get("turn_id")),
            "turn_count": turn_payload.get("turn_count"),
            "state_summary_present": "state_summary" in turn_payload,
            "next_question": turn_payload.get("next_question"),
            "metadata": turn_payload.get("metadata"),
        },
        "state_contract": {
            "status_code": state["status_code"],
            "turn_count": state_payload.get("turn_count"),
            "missing_core_fields": state_payload.get("missing_core_fields"),
        },
        "high_risk_contract": {
            "status_code": high_risk_turn["status_code"],
            "risk_flags_status": high_risk_payload.get("risk_flags_status"),
            "risk_rule_ids": high_risk_payload.get("risk_rule_ids"),
            "risk_reasons": high_risk_payload.get("risk_reasons"),
        },
        "checks": checks,
        "live_vllm_smoke": {
            "status": "skipped",
            "reason": "RUN_LOCAL_VLLM_SMOKE is not enabled",
        },
        "git_status_short": _git(["status", "--short"]).splitlines(),
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Verify P12 session, turn, state, and health API contract.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Artifact output path.")
    args = parser.parse_args()
    payload = verify()
    if args.output:
        _write_json(Path(args.output), payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(json.dumps({"stage": payload["stage"], "status": payload["status"]}, indent=2))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
