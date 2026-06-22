from __future__ import annotations

import os
import uuid
from typing import Any

from app.graph.builder import P9_NODE_SEQUENCE
from app.graph.runtime import run_fallback_runtime, run_langgraph_runtime
from app.graph.state import ConsultationGraphState
from app.schemas.report_schemas import RunState


def _initial_state(
    user_input: str,
    *,
    run_state: RunState | None,
    session_id: str | None,
    extractor_backend: str | None,
    rag_enabled: bool,
) -> ConsultationGraphState:
    selected_backend = extractor_backend or os.getenv("EXTRACTOR_BACKEND") or "fake"
    return ConsultationGraphState(
        session_id=session_id or f"p9m1-{uuid.uuid4().hex[:12]}",
        user_input=user_input,
        run_state=run_state or RunState(),
        extractor_mode_requested=selected_backend,
        rag_enabled=rag_enabled,
    )


def run_p9m1_graph(
    user_input: str,
    *,
    run_state: RunState | None = None,
    session_id: str | None = None,
    extractor_backend: str | None = None,
    rag_enabled: bool = True,
    use_langgraph: bool = True,
) -> dict[str, Any]:
    initial_state = _initial_state(
        user_input,
        run_state=run_state,
        session_id=session_id,
        extractor_backend=extractor_backend,
        rag_enabled=rag_enabled,
    )

    graph_runtime = "sequential_fallback"
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
    result = dict(state.exported_result)
    result["graph_runtime"] = graph_runtime
    result["trace"] = list(state.trace)
    result["errors"] = list(state.errors)
    result["run_state"] = state.run_state.model_dump()
    result["final_report"] = state.final_report.model_dump() if state.final_report else None
    return result


__all__ = ["run_p9m1_graph"]
