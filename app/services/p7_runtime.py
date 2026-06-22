from __future__ import annotations

from typing import Any

from app.api.report_validator import validate_report
from app.memory.manager import MemoryManager
from app.observability.trace import build_p7_trace_event
from app.rag.evidence_schema import P6EvidencePack, evidence_pack_to_storage_records
from app.schemas.report_schemas import RunState
from app.storage.models import (
    AuditLogRecord,
    FinalReportRecord,
    MemorySnapshotRecord,
    RiskEventRecord,
    RunStateSnapshot,
    StorageSession,
    StorageTurn,
    TraceEventRecord,
)
from app.storage.sqlite_store import P7SQLiteStore, get_default_store


def _model_dump(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return value
    return {"value": value}


def _latest_p6_pack(graph_output: dict[str, Any]) -> P6EvidencePack | None:
    payload = graph_output.get("p6b_rag_evidence_pack")
    if not payload:
        return None
    try:
        return P6EvidencePack.model_validate(payload)
    except Exception:
        return None


def _used_chunk_ids(run_state: RunState) -> set[str]:
    report = run_state.final_report
    if report is None:
        return set()
    references = report.metadata.get("p6b_evidence_references") if isinstance(report.metadata, dict) else []
    if not isinstance(references, list):
        return set()
    return {str(item.get("chunk_id")) for item in references if isinstance(item, dict) and item.get("chunk_id")}


def record_session(session: Any, *, store: P7SQLiteStore | None = None) -> None:
    target = store or get_default_store()
    target.create_session(
        StorageSession(
            session_id=session.session_id,
            created_at=session.created_at,
            updated_at=session.updated_at,
            mode=session.extractor_mode,
            rag_enabled=bool(session.rag_enabled),
            metadata={"phase": "P7", "source": "api_session"},
        )
    )


def record_turn(
    *,
    session: Any,
    previous_state: RunState,
    user_input: str,
    graph_output: dict[str, Any],
    turn_id: str,
    latency_ms: int,
    store: P7SQLiteStore | None = None,
) -> dict[str, Any]:
    target = store or get_default_store()
    record_session(session, store=target)
    run_state = graph_output.get("run_state") or session.run_state
    if not isinstance(run_state, RunState):
        run_state = RunState.model_validate(_model_dump(run_state))

    memory_snapshot = MemoryManager().build_snapshot(
        session_id=session.session_id,
        turn_id=turn_id,
        turn_index=int(session.turn_count),
        previous_state=previous_state,
        current_state=run_state,
        user_input=user_input,
    )
    p6_pack = _latest_p6_pack(graph_output)
    evidence_records = []
    if p6_pack is not None:
        evidence_records = evidence_pack_to_storage_records(
            p6_pack,
            session_id=session.session_id,
            turn_id=turn_id,
            used_chunk_ids=_used_chunk_ids(run_state),
            used_in_report_section="report.metadata",
        )
    p7_trace = build_p7_trace_event(
        session_id=session.session_id,
        turn_id=turn_id,
        api_route="POST /sessions/{session_id}/turn",
        run_state=run_state,
        graph_output=graph_output,
        storage_write_pass=True,
        memory_write_pass=True,
        latency_ms=latency_ms,
    )
    target.append_turn_bundle(
        turn=StorageTurn(
            turn_id=turn_id,
            session_id=session.session_id,
            turn_index=int(session.turn_count),
            user_input=user_input,
            turn_output=_model_dump(graph_output.get("turn_output")),
        ),
        run_state=RunStateSnapshot(
            session_id=session.session_id,
            turn_id=turn_id,
            state=run_state.model_dump(),
        ),
        risk_events=[
            RiskEventRecord(
                session_id=session.session_id,
                turn_id=turn_id,
                risk_status=run_state.risk_flags_status,
                rule_ids=list(run_state.triggered_rule_ids),
                reasons=list(run_state.risk_reasons),
            )
        ],
        rag_evidence=evidence_records,
        memory_snapshot=MemorySnapshotRecord(
            session_id=session.session_id,
            turn_id=turn_id,
            snapshot=memory_snapshot.model_dump(),
        ),
        trace_event=TraceEventRecord(
            session_id=session.session_id,
            turn_id=turn_id,
            trace_id=p7_trace.trace_id,
            event=p7_trace.model_dump(),
        ),
        audit_logs=[
            AuditLogRecord(
                session_id=session.session_id,
                turn_id=turn_id,
                event_type="turn.persisted",
                payload={"phase": "P7", "storage_write_pass": True},
            )
        ],
    )
    return {
        "trace_id": p7_trace.trace_id,
        "memory_write_pass": memory_snapshot.memory_write_pass,
        "rag_evidence_count": len(evidence_records),
    }


def record_report(
    *,
    session: Any,
    turn_id: str,
    store: P7SQLiteStore | None = None,
) -> dict[str, Any]:
    target = store or get_default_store()
    run_state = session.run_state
    final_report = run_state.final_report
    if final_report is None:
        return {"status": "not_ready", "trace_id": ""}
    report_payload = final_report.model_dump()
    state_payload = run_state.model_dump()
    safety_check = validate_report(report_payload, state_payload)
    p7_trace = build_p7_trace_event(
        session_id=session.session_id,
        turn_id=turn_id,
        api_route="POST /sessions/{session_id}/report",
        run_state=run_state,
        storage_write_pass=True,
        memory_write_pass=True,
    )
    target.save_final_report_bundle(
        report=FinalReportRecord(
            session_id=session.session_id,
            turn_id=turn_id,
            report=report_payload,
            safety_check=safety_check,
        ),
        audit_logs=[
            AuditLogRecord(
                session_id=session.session_id,
                turn_id=turn_id,
                event_type="report.persisted",
                payload={"phase": "P7", "safety_check": safety_check},
            )
        ],
        trace_event=TraceEventRecord(
            session_id=session.session_id,
            turn_id=turn_id,
            trace_id=p7_trace.trace_id,
            event=p7_trace.model_dump(),
        ),
    )
    return {"status": "ok", "trace_id": p7_trace.trace_id, "safety_check": safety_check}
