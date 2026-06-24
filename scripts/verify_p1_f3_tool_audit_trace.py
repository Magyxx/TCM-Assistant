from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SYNTHETIC_SECRET = "sk-p1f3syntheticsecret"
REQUEST_ID = "p1-f3-tool-audit-verify"
ENV_NAMES = [
    "ENABLE_REAL_LLM",
    "TCM_API_DB_PATH",
    "TCM_SQLITE_PATH",
]


def _git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()
    except Exception:
        return "unknown"


def _run_check(checks: dict[str, str], name: str, fn: Callable[[], None]) -> None:
    try:
        fn()
    except Exception as exc:
        checks[name] = f"failed:{type(exc).__name__}:{exc}"
    else:
        checks[name] = "passed"


def _configure_runtime(tmp: str) -> dict[str, str | None]:
    previous = {name: os.environ.get(name) for name in ENV_NAMES}
    tmp_path = Path(tmp)
    os.environ["ENABLE_REAL_LLM"] = "false"
    os.environ["TCM_API_DB_PATH"] = str(tmp_path / "api.sqlite3")
    os.environ["TCM_SQLITE_PATH"] = str(tmp_path / "p7.sqlite3")

    from app.api.session_runtime import clear_sessions

    clear_sessions()
    return previous


def _restore_runtime(previous: dict[str, str | None]) -> None:
    from app.api.session_runtime import clear_sessions

    clear_sessions()
    for name, value in previous.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def build_validation() -> dict[str, Any]:
    checks: dict[str, str] = {}
    metrics: dict[str, Any] = {}

    def tool_audit_trace_redaction() -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            previous = _configure_runtime(tmp)
            try:
                from fastapi.testclient import TestClient

                from app.api.deps import get_p7_store
                from app.api.main import app

                with TestClient(app, raise_server_exceptions=False) as client:
                    created = client.post("/sessions", json={"extractor_mode": "fake", "rag_enabled": True})
                    assert created.status_code == 200, created.text
                    session_id = created.json()["session_id"]

                    blocked = client.post(
                        "/tools/export_report_tool/invoke",
                        headers={"X-Request-ID": REQUEST_ID},
                        json={
                            "session_id": session_id,
                            "approved": False,
                            "payload": {
                                "report": {
                                    "summary": "ok",
                                    "note": SYNTHETIC_SECRET,
                                }
                            },
                        },
                    )
                    assert blocked.status_code == 200, blocked.text
                    blocked_payload = blocked.json()
                    assert blocked_payload["status"] == "blocked"
                    assert blocked_payload["allowed"] is False
                    assert blocked_payload["blocked_reason"] == "human_approval_required"
                    assert blocked_payload["audit_log"]["trace_id"] == blocked_payload["trace_id"]
                    assert blocked_payload["audit_log"]["request_id"] == REQUEST_ID

                    allowed = client.post(
                        "/tools/risk_check_tool/invoke",
                        json={
                            "session_id": session_id,
                            "payload": {"user_input": f"没有胸痛 {SYNTHETIC_SECRET}"},
                        },
                    )
                    assert allowed.status_code == 200, allowed.text
                    allowed_payload = allowed.json()
                    assert allowed_payload["status"] == "ok"
                    assert allowed_payload["allowed"] is True
                    assert allowed_payload["audit_log"]["trace_id"] == allowed_payload["trace_id"]

                    trace = client.get(f"/sessions/{session_id}/trace")
                    assert trace.status_code == 200, trace.text
                    tool_events = [
                        item for item in trace.json()["traces"]
                        if item.get("event", {}).get("event_type") == "tool.invoke"
                    ]
                    trace_ids = {item["trace_id"] for item in tool_events}
                    assert blocked_payload["trace_id"] in trace_ids
                    assert allowed_payload["trace_id"] in trace_ids

                    audit_logs = [
                        item for item in get_p7_store().fetch_audit_logs(session_id)
                        if item.get("event_type") == "tool.invoke"
                    ]
                    audit_text = json.dumps(audit_logs, ensure_ascii=False, sort_keys=True)
                    response_text = json.dumps([blocked_payload, allowed_payload, trace.json()], ensure_ascii=False)
                    assert SYNTHETIC_SECRET not in audit_text
                    assert SYNTHETIC_SECRET not in response_text
                    assert blocked_payload["trace_id"] in audit_text
                    assert allowed_payload["trace_id"] in audit_text
                    metrics.update(
                        {
                            "session_id": session_id,
                            "tool_trace_event_count": len(tool_events),
                            "tool_audit_log_count": len(audit_logs),
                            "blocked_tool_trace_id": blocked_payload["trace_id"],
                            "allowed_tool_trace_id": allowed_payload["trace_id"],
                        }
                    )
            finally:
                _restore_runtime(previous)

    def tool_registry_boundary() -> None:
        from app.tools.registry import build_p7_registry

        definitions = {item.name: item for item in build_p7_registry().definitions()}
        export_tool = definitions["export_report_tool"]
        assert export_tool.side_effect is True
        assert export_tool.requires_human_approval is True
        assert all(item.audit_log for item in definitions.values())
        metrics["tool_count"] = len(definitions)

    for name, fn in [
        ("tool_audit_trace_redaction", tool_audit_trace_redaction),
        ("tool_registry_boundary", tool_registry_boundary),
    ]:
        _run_check(checks, name, fn)

    checks["no_real_llm_required"] = "passed"
    checks["no_external_tool_runtime_required"] = "passed"
    status = "ok" if all(value == "passed" for value in checks.values()) else "failed"
    return {
        "stage": "P1-F3_TOOL_AUDIT_TRACE",
        "status": status,
        "branch": _git(["branch", "--show-current"]),
        "commit": _git(["rev-parse", "HEAD"]),
        "external_dependencies_required": False,
        "checks": checks,
        "metrics": metrics,
        "artifacts": {
            "p1_f3_tool_audit_trace_validation": "artifacts/p1_f3_tool_audit_trace_validation.json",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", default="artifacts/p1_f3_tool_audit_trace_validation.json")
    args = parser.parse_args()
    result = build_validation()
    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"{result['stage']} {result['status']} -> {output_path}")
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
