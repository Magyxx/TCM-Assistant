from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Any

from app.graph.builder import P9_NODE_SEQUENCE
from app.graph.runtime import run_fallback_runtime, run_langgraph_runtime
from app.graph.state import ConsultationGraphState
from app.observability.events import GraphEvent, redacted_input_hash
from app.observability.json_logger import DEFAULT_GRAPH_EVENTS_PATH, append_graph_events
from app.schemas.report_schemas import RunState
from app.session.store import SessionStore


def _initial_state(
    user_input: str,
    *,
    run_state: RunState | None,
    session_id: str | None,
    trace_id: str | None,
    turn_id: str | None,
    extractor_backend: str | None,
    rag_enabled: bool,
) -> ConsultationGraphState:
    selected_backend = extractor_backend or os.getenv("EXTRACTOR_BACKEND") or "fake"
    return ConsultationGraphState(
        session_id=session_id or f"p9m2-{uuid.uuid4().hex[:12]}",
        trace_id=trace_id or f"trace-{uuid.uuid4().hex[:12]}",
        turn_id=turn_id or f"turn-{(run_state.turn_count + 1) if run_state else 1}",
        user_input=user_input,
        run_state=run_state or RunState(),
        extractor_mode_requested=selected_backend,
        rag_enabled=rag_enabled,
    )


def _coerce_state(payload: dict[str, Any] | None) -> RunState | None:
    if not payload:
        return None
    return RunState.model_validate(payload)


def _graph_events_from_state(
    state: ConsultationGraphState,
    *,
    graph_runtime: str,
    total_latency_ms: int,
) -> list[GraphEvent]:
    events: list[GraphEvent] = []
    for item in state.trace:
        node = str(item.get("node") or "unknown")
        events.append(
            GraphEvent(
                trace_id=state.trace_id,
                session_id=state.session_id,
                turn_id=state.turn_id,
                node=node,
                graph_runtime=graph_runtime,
                extractor_mode=state.extractor_mode or state.extractor_mode_requested,
                raw_llm_json_valid=state.raw_llm_json_valid,
                final_schema_pass=state.final_schema_pass,
                fallback_used=state.fallback_used,
                risk_rule_ids=list(state.run_state.triggered_rule_ids),
                retrieved_evidence_count=state.retrieved_evidence_count,
                safety_rewrite_used=bool(state.safety_issues),
                latency_ms=total_latency_ms if node == "export_result" else 0,
                input_length=len(state.user_input or ""),
                redacted_input_hash=redacted_input_hash(state.user_input or ""),
                metadata={key: value for key, value in item.items() if key not in {"node"}},
            )
        )
    return events


def _persist_run(
    state: ConsultationGraphState,
    *,
    graph_runtime: str,
    total_latency_ms: int,
    session_store: SessionStore | None,
    graph_events_path: str | Path | None,
) -> tuple[list[dict[str, Any]], str | None]:
    events = _graph_events_from_state(state, graph_runtime=graph_runtime, total_latency_ms=total_latency_ms)
    event_dicts = [event.model_dump() for event in events]
    output_path = append_graph_events(events, graph_events_path or DEFAULT_GRAPH_EVENTS_PATH)

    if session_store is not None:
        session_store.create_session(state.session_id)
        session_store.append_turn(
            state.session_id,
            "user",
            state.user_input,
            turn_id=state.turn_id,
            metadata={
                "trace_id": state.trace_id,
                "input_length": len(state.user_input or ""),
                "redacted_input_hash": redacted_input_hash(state.user_input or ""),
            },
        )
        assistant_content = state.next_question or (state.final_report.summary if state.final_report else "")
        if assistant_content:
            session_store.append_turn(
                state.session_id,
                "assistant",
                assistant_content,
                turn_id=f"{state.turn_id}-assistant",
                metadata={"trace_id": state.trace_id},
            )
        session_store.save_state(state.session_id, state.run_state)
        for event in state.risk_events:
            session_store.save_event(state.session_id, {"event_type": "risk_event", **event})
        for chunk in state.p9_evidence:
            session_store.save_event(state.session_id, {"event_type": "rag_evidence", **chunk.model_dump()})
        if state.final_report is not None:
            session_store.save_event(
                state.session_id,
                {"event_type": "final_report", "report": state.final_report.model_dump()},
            )
        for event in event_dicts:
            session_store.save_event(state.session_id, {"event_type": "graph_event", **event})
    return event_dicts, str(output_path)


def run_p9m1_graph(
    user_input: str,
    *,
    run_state: RunState | None = None,
    session_id: str | None = None,
    trace_id: str | None = None,
    turn_id: str | None = None,
    extractor_backend: str | None = None,
    rag_enabled: bool = True,
    use_langgraph: bool = True,
    session_store: SessionStore | None = None,
    graph_events_path: str | Path | None = None,
) -> dict[str, Any]:
    if session_store is not None and session_id and run_state is None:
        run_state = _coerce_state(session_store.load_state(session_id))
        if turn_id is None:
            user_turns = [turn for turn in session_store.list_turns(session_id) if turn.role == "user"]
            turn_id = f"turn-{len(user_turns) + 1}"
    initial_state = _initial_state(
        user_input,
        run_state=run_state,
        session_id=session_id,
        trace_id=trace_id,
        turn_id=turn_id,
        extractor_backend=extractor_backend,
        rag_enabled=rag_enabled,
    )

    graph_runtime = "sequential_fallback"
    started = time.perf_counter()
    if use_langgraph:
        try:
            state = run_langgraph_runtime(initial_state, P9_NODE_SEQUENCE)
            graph_runtime = "langgraph"
        except Exception as exc:
            initial_state.errors.append(f"langgraph_runtime_failed:{exc.__class__.__name__}")
            state = run_fallback_runtime(initial_state, P9_NODE_SEQUENCE)
    else:
        state = run_fallback_runtime(initial_state, P9_NODE_SEQUENCE)

    state.graph_runtime = graph_runtime
    total_latency_ms = int((time.perf_counter() - started) * 1000)
    graph_events, graph_events_output_path = _persist_run(
        state,
        graph_runtime=graph_runtime,
        total_latency_ms=total_latency_ms,
        session_store=session_store,
        graph_events_path=graph_events_path,
    )
    result = dict(state.exported_result)
    result["graph_runtime"] = graph_runtime
    result["trace_id"] = state.trace_id
    result["turn_id"] = state.turn_id
    result["trace"] = list(state.trace)
    result["graph_events"] = graph_events
    result["graph_events_path"] = graph_events_output_path
    result["errors"] = list(state.errors)
    result["run_state"] = state.run_state.model_dump()
    result["final_report"] = state.final_report.model_dump() if state.final_report else None
    return result


__all__ = ["run_p9m1_graph"]
