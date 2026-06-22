from __future__ import annotations

import os
from typing import Callable, List, Tuple

from app.graph.nodes import (
    extract_turn_node,
    memory_update,
    normalize_input,
    plan_next_action,
    risk_check,
    validate_turn,
)
from app.graph.runtime import build_langgraph_runtime, run_fallback_runtime, run_langgraph_runtime
from app.graph.state import ConsultationGraphState
from app.memory.manager import MemoryManager
from app.memory.models import ConsultationMemory
from app.schemas.report_schemas import RunState


NODE_SEQUENCE: List[Tuple[str, Callable[[ConsultationGraphState], ConsultationGraphState]]] = [
    ("normalize_input", normalize_input),
    ("extract_turn", extract_turn_node),
    ("validate_turn", validate_turn),
    ("memory_update", memory_update),
    ("risk_check", risk_check),
    ("plan_next_action", plan_next_action),
]


def build_consultation_graph():
    return build_langgraph_runtime(NODE_SEQUENCE)


def _memory_from_run_state(run_state: RunState) -> ConsultationMemory:
    existing = run_state.metadata.get("p8_memory") if isinstance(run_state.metadata, dict) else None
    if isinstance(existing, dict):
        return ConsultationMemory.model_validate(existing)
    return MemoryManager().from_run_state(run_state)


def _initial_state(
    run_state: RunState | None,
    user_input: str,
    *,
    extractor_mode: str,
    rag_enabled: bool,
) -> ConsultationGraphState:
    base_state = run_state or RunState()
    return ConsultationGraphState(
        run_state=base_state,
        memory=_memory_from_run_state(base_state),
        user_input=user_input,
        extractor_mode_requested=extractor_mode,
        rag_enabled=rag_enabled,
    )


def _finalize_state(
    state: ConsultationGraphState,
    *,
    graph_runtime: str,
    extractor_mode_requested: str,
) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    updated.graph_runtime = graph_runtime
    updated.extractor_mode_requested = extractor_mode_requested
    updated.run_state.metadata = {
        **updated.run_state.metadata,
        "graph_runtime": graph_runtime,
        "extractor_mode_requested": extractor_mode_requested,
        "last_extractor_mode": updated.extractor_mode,
        "last_extraction_mode": updated.extraction_mode,
        "last_strategy": updated.strategy,
        "last_model_name": updated.model_name,
        "last_error_type": updated.error_type,
        "last_error_message_preview": updated.error_message_preview,
        "last_fallback_used": updated.fallback_used,
        "last_final_schema_pass": updated.final_schema_pass,
        "p8_graph": {
            "runtime": graph_runtime,
            "node_sequence": [name for name, _ in NODE_SEQUENCE],
            "memory_update_used": True,
            "risk_rule_first": True,
            "fallback_runtime_available": True,
        },
    }
    return updated


def run_consultation_graph(
    run_state: RunState | None,
    user_input: str,
    use_langgraph: bool = True,
    extractor_mode: str | None = None,
    rag_enabled: bool = True,
) -> dict:
    requested_mode = extractor_mode or os.getenv("TCM_EXTRACTOR_MODE", "auto")
    initial_state = _initial_state(
        run_state,
        user_input,
        extractor_mode=requested_mode,
        rag_enabled=rag_enabled,
    )

    if use_langgraph:
        try:
            graph_state = run_langgraph_runtime(initial_state, NODE_SEQUENCE)
            return _finalize_state(
                graph_state,
                graph_runtime="langgraph",
                extractor_mode_requested=requested_mode,
            ).to_legacy_dict()
        except Exception as exc:
            initial_state.errors.append(f"langgraph_runtime_failed:{exc.__class__.__name__}")

    graph_state = run_fallback_runtime(initial_state, NODE_SEQUENCE)
    return _finalize_state(
        graph_state,
        graph_runtime="sequential_fallback",
        extractor_mode_requested=requested_mode,
    ).to_legacy_dict()


__all__ = ["NODE_SEQUENCE", "build_consultation_graph", "run_consultation_graph"]
