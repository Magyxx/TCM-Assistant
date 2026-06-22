from __future__ import annotations

from typing import Any

try:
    from p7_common import ROOT_DIR, check, status_from_checks, write_json
except ImportError:  # pragma: no cover - package import path
    from scripts.p7_common import ROOT_DIR, check, status_from_checks, write_json

from app.observability.metrics import summarize_trace_metrics  # noqa: E402
from app.observability.trace import build_p7_trace_event, p7_trace_schema_pass  # noqa: E402
from app.schemas.report_schemas import RunState  # noqa: E402
from app.storage.models import StorageSession, StorageTurn, RunStateSnapshot, TraceEventRecord  # noqa: E402
from app.storage.sqlite_store import P7SQLiteStore  # noqa: E402


ARTIFACT = ROOT_DIR / "artifacts" / "p7_observability_validation.json"
TRACE_ARTIFACT = ROOT_DIR / "artifacts" / "p7_trace_samples.json"


def run_p7_observability_validation(*, write_artifact: bool = True) -> dict[str, Any]:
    run_state = RunState(chief_complaint="胃胀", duration="一周", risk_flags_status="none", turn_count=1)
    trace = build_p7_trace_event(
        session_id="p7-trace-session",
        turn_id="1",
        api_route="POST /sessions/{session_id}/turn",
        run_state=run_state,
        graph_output={"graph_runtime": "langgraph", "extractor_mode": "fake"},
        storage_write_pass=True,
        memory_write_pass=True,
        latency_ms=12,
    )
    store = P7SQLiteStore(ROOT_DIR / ".runtime" / "p7_observability.sqlite3")
    store.create_session(StorageSession(session_id="p7-trace-session", mode="fake"))
    store.append_turn_bundle(
        turn=StorageTurn(turn_id="1", session_id="p7-trace-session", turn_index=1, user_input="胃胀一周"),
        run_state=RunStateSnapshot(session_id="p7-trace-session", turn_id="1", state=run_state.model_dump()),
        trace_event=TraceEventRecord(
            session_id="p7-trace-session",
            turn_id="1",
            trace_id=trace.trace_id,
            event=trace.model_dump(),
        ),
    )
    stored = [item["event"] for item in store.fetch_trace_events("p7-trace-session")]
    metrics = summarize_trace_metrics(stored)
    checks = [
        check("trace_schema_pass", p7_trace_schema_pass([trace.model_dump()]) and metrics["trace_schema_pass"]),
        check("trace_storage_pass", metrics["trace_storage_pass"]),
        check("fallback_recorded", "fallback_used" in trace.model_dump() and "fallback_reason" in trace.model_dump()),
        check("storage_status_not_faked", store.table_counts()["trace_events"] >= 1),
    ]
    payload = {
        "phase": "P7",
        "status": status_from_checks(checks),
        "checks": checks,
        "metrics": metrics,
        "trace_samples": stored,
    }
    if write_artifact:
        write_json(ARTIFACT, payload)
        write_json(TRACE_ARTIFACT, {"phase": "P7", "traces": stored, "sample_count": len(stored)})
    return payload


def main() -> int:
    payload = run_p7_observability_validation()
    print(f"P7 observability validation: status={payload['status']} artifact={ARTIFACT.relative_to(ROOT_DIR)}")
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
