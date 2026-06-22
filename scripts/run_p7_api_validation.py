from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

try:
    from p7_common import ROOT_DIR, check, status_from_checks, write_json
except ImportError:  # pragma: no cover - package import path
    from scripts.p7_common import ROOT_DIR, check, status_from_checks, write_json

os.environ.setdefault("TCM_API_DB_PATH", str(ROOT_DIR / ".runtime" / "p7_api_contract.sqlite3"))
os.environ.setdefault("TCM_SQLITE_PATH", str(ROOT_DIR / ".runtime" / "p7_api.sqlite3"))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.main import app  # noqa: E402
from app.api.session_runtime import clear_session_cache, clear_sessions  # noqa: E402
from app.storage.sqlite_store import get_default_store  # noqa: E402


ARTIFACT = ROOT_DIR / "artifacts" / "p7_api_validation.json"


def run_p7_api_validation(*, write_artifact: bool = True) -> dict[str, Any]:
    clear_sessions()
    client = TestClient(app, raise_server_exceptions=False)
    health = client.get("/health")
    version = client.get("/version")
    created = client.post("/sessions", json={"extractor_mode": "fake", "rag_enabled": True})
    session_payload = created.json() if created.status_code == 200 else {}
    session_id = str(session_payload.get("session_id") or "")
    detail = client.get(f"/sessions/{session_id}") if session_id else None
    turn = client.post(
        f"/sessions/{session_id}/turn",
        json={"user_input": "胃胀一周，没有其他症状，也没有胸痛，没有呼吸困难，没有便血"},
    ) if session_id else None
    state = client.get(f"/sessions/{session_id}/state") if session_id else None
    report_post = client.post(f"/sessions/{session_id}/report") if session_id else None
    report_get = client.get(f"/sessions/{session_id}/report") if session_id else None
    trace = client.get(f"/sessions/{session_id}/trace") if session_id else None
    evidence = client.get(f"/sessions/{session_id}/evidence") if session_id else None
    tools = client.get("/tools")
    eval_response = client.post("/eval/p7", json={"case": {"turns": ["胃胀"], "expected": {}}})

    clear_session_cache()
    restored = client.get(f"/sessions/{session_id}/state") if session_id else None
    store_counts = get_default_store().table_counts()
    trace_payload = trace.json() if trace is not None and trace.status_code == 200 else {}
    evidence_payload = evidence.json() if evidence is not None and evidence.status_code == 200 else {}
    detail_payload = detail.json() if detail is not None and detail.status_code == 200 else {}
    tools_payload = tools.json() if tools.status_code == 200 else {}
    eval_payload = eval_response.json() if eval_response.status_code == 200 else {}
    turn_payload = turn.json() if turn is not None and turn.status_code == 200 else {}
    turn_metadata = turn_payload.get("metadata") or {}

    checks = [
        check("api_health_ok", health.status_code == 200 and health.json().get("status") == "ok"),
        check("api_version_ok", version.status_code == 200),
        check("api_session_create_ok", created.status_code == 200 and bool(session_id)),
        check("api_session_get_ok", detail is not None and detail.status_code == 200),
        check("api_turn_ok", turn is not None and turn.status_code == 200),
        check("api_state_ok", state is not None and state.status_code == 200),
        check("api_report_ok", report_post is not None and report_post.status_code == 200 and report_get is not None and report_get.status_code == 200),
        check("api_trace_ok", trace is not None and trace.status_code == 200 and len(trace_payload.get("traces") or []) >= 1),
        check("api_evidence_ok", evidence is not None and evidence.status_code == 200),
        check("api_tools_ok", tools.status_code == 200 and len(tools.json().get("tools") or []) == 5),
        check("api_eval_ok", eval_response.status_code == 200 and eval_response.json().get("status") == "ok"),
        check("api_state_restore_ok", restored is not None and restored.status_code == 200),
        check("api_response_trace_status_ok", all(
            "trace_id" in payload and "status" in payload
            for payload in [
                detail_payload,
                trace_payload,
                evidence_payload,
                tools_payload,
                eval_payload,
            ]
        ) and bool(turn_metadata.get("p7_trace_id")) and turn_metadata.get("p7_status") == "ok"),
    ]
    metrics = {
        item["name"]: item["ok"] for item in checks
    }
    metrics.update(
        {
            "retrieved_evidence_count": len(evidence_payload.get("retrieved_evidence") or []),
            "used_evidence_count": len(evidence_payload.get("used_evidence") or []),
            "trace_event_count": len(trace_payload.get("traces") or []),
            "storage_table_counts": store_counts,
        }
    )
    payload = {
        "phase": "P7",
        "status": status_from_checks(checks),
        "session_id": session_id,
        "checks": checks,
        "metrics": metrics,
    }
    if write_artifact:
        write_json(ARTIFACT, payload)
    return payload


def main() -> int:
    payload = run_p7_api_validation()
    print(f"P7 API validation: status={payload['status']} artifact={ARTIFACT.relative_to(ROOT_DIR)}")
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
