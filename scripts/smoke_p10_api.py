from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

P10_DIR = ROOT_DIR / "artifacts" / "p10"
SMOKE_RESULT_PATH = P10_DIR / "api_smoke_result.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _safe_json(response) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception:
        return {"raw_text": response.text[-1000:]}
    return payload if isinstance(payload, dict) else {"payload": payload}


def run_smoke() -> dict[str, Any]:
    os.environ.setdefault("EXTRACTOR_BACKEND", "fake")
    os.environ.setdefault("ENABLE_REAL_LLM", "false")
    os.environ.setdefault("SESSION_STORE_BACKEND", "sqlite")
    os.environ.setdefault("SESSION_SQLITE_PATH", str(P10_DIR / "p10_sessions.sqlite3"))
    os.environ.setdefault("API_LOG_PATH", str(P10_DIR / "api_events.jsonl"))
    os.environ.setdefault("TCM_API_DB_PATH", str(P10_DIR / "p10_legacy_api.sqlite3"))
    os.environ.setdefault("TCM_SQLITE_PATH", str(P10_DIR / "p10_p7.sqlite3"))

    from app.api.main import app

    client = TestClient(app, raise_server_exceptions=False)
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}

    health = client.get("/health?extended=true")
    checks["health_passed"] = health.status_code == 200 and health.json().get("status") == "ok"
    details["health"] = _safe_json(health)

    created = client.post("/sessions", json={"metadata": {"source": "p10_smoke"}, "backend": "fake"})
    session_payload = _safe_json(created)
    session_id = str(session_payload.get("session_id") or "")
    checks["session_create_passed"] = created.status_code == 200 and bool(session_id)
    details["session"] = session_payload

    turn = client.post(
        f"/sessions/{session_id}/turn",
        json={
            "user_input": "最近胃胀，饭后明显，差不多一周，没有发热，也不胸痛",
            "extractor_backend": "fake",
            "metadata": {"source": "p10_smoke"},
        },
    )
    turn_payload = _safe_json(turn)
    checks["turn_passed"] = turn.status_code == 200 and turn_payload.get("session_id") == session_id
    details["turn"] = turn_payload

    state = client.get(f"/sessions/{session_id}/state")
    checks["state_passed"] = state.status_code == 200 and state.json().get("session_id") == session_id
    details["state"] = _safe_json(state)

    report = client.get(f"/sessions/{session_id}/report")
    report_payload = _safe_json(report)
    checks["report_passed"] = report.status_code == 200 and report_payload.get("session_id") == session_id
    details["report"] = report_payload

    replay = client.post(f"/sessions/{session_id}/replay", json={"allow_write": False})
    replay_payload = _safe_json(replay)
    checks["replay_passed"] = replay.status_code == 200 and replay_payload.get("replay_status") == "ok_read_only"
    details["replay"] = replay_payload

    result = {
        "status": "ok" if all(checks.values()) else "failed",
        "session_id": session_id,
        "checks": checks,
        "summary": {
            "turn_risk_status": turn_payload.get("risk_status"),
            "missing_core_fields": turn_payload.get("missing_core_fields", []),
            "report_available": report_payload.get("report_available"),
            "replay_turn_count": len(replay_payload.get("turns") or []),
        },
        "details": details,
    }
    _write_json(SMOKE_RESULT_PATH, result)
    return result


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    result = run_smoke()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
