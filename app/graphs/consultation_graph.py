from __future__ import annotations

import os
from typing import Callable, List, Tuple

from app.graphs.consultation_nodes import (
    ask_followup,
    decide_next,
    extract_turn_node,
    generate_report,
    merge_state,
    normalize_input,
    retrieve_knowledge,
    risk_rule_check,
    safety_post_check,
    validate_turn,
)
from app.graphs.consultation_state import ConsultationGraphState
from app.schemas.report_schemas import RunState


NODE_SEQUENCE: List[Tuple[str, Callable[[ConsultationGraphState], ConsultationGraphState]]] = [
    ("normalize_input", normalize_input),
    ("extract_turn", extract_turn_node),
    ("validate_turn", validate_turn),
    ("merge_state", merge_state),
    ("risk_rule_check", risk_rule_check),
    ("decide_next", decide_next),
    ("ask_followup", ask_followup),
    ("retrieve_knowledge", retrieve_knowledge),
    ("generate_report", generate_report),
    ("safety_post_check", safety_post_check),
]


def build_consultation_graph():
    try:
        from langgraph.graph import END, StateGraph
    except Exception:
        return None

    graph = StateGraph(ConsultationGraphState)
    for node_name, node_func in NODE_SEQUENCE:
        graph.add_node(node_name, node_func)

    graph.set_entry_point(NODE_SEQUENCE[0][0])
    for (current_name, _), (next_name, _) in zip(NODE_SEQUENCE, NODE_SEQUENCE[1:]):
        graph.add_edge(current_name, next_name)
    graph.add_edge(NODE_SEQUENCE[-1][0], END)
    return graph.compile()


def _run_sequential_fallback(initial_state: ConsultationGraphState) -> ConsultationGraphState:
    state = initial_state
    for _, node_func in NODE_SEQUENCE:
        state = node_func(state)
    return state


def _finalize_graph_state(
    state: ConsultationGraphState,
    graph_runtime: str,
    extractor_mode_requested: str,
) -> ConsultationGraphState:
    run_state = state.get("run_state") or RunState()
    run_state = run_state.model_copy(deep=True)
    run_state.metadata = {
        **run_state.metadata,
        "graph_runtime": graph_runtime,
        "extractor_mode_requested": extractor_mode_requested,
        "last_extractor_mode": state.get("extractor_mode"),
        "last_extraction_mode": state.get("extraction_mode"),
        "last_strategy": state.get("strategy"),
        "last_model_name": state.get("model_name"),
        "last_error_type": state.get("error_type"),
        "last_error_message_preview": state.get("error_message_preview"),
        "last_fallback_used": state.get("fallback_used"),
        "last_final_schema_pass": state.get("final_schema_pass"),
    }
    if run_state.final_report is not None:
        run_state.final_report.metadata = {
            **run_state.final_report.metadata,
            "graph_runtime": graph_runtime,
            "extractor_mode_requested": extractor_mode_requested,
            "extractor_mode": state.get("extractor_mode"),
            "strategy": state.get("strategy"),
            "fallback_used": state.get("fallback_used"),
            "final_schema_pass": state.get("final_schema_pass"),
            "error_type": state.get("error_type"),
        }

    return {
        **state,
        "run_state": run_state,
        "graph_runtime": graph_runtime,
        "extractor_mode_requested": extractor_mode_requested,
    }


def run_consultation_graph(
    run_state: RunState | None,
    user_input: str,
    use_langgraph: bool = True,
    extractor_mode: str | None = None,
    rag_enabled: bool = True,
) -> ConsultationGraphState:
    requested_mode = extractor_mode or os.getenv("TCM_EXTRACTOR_MODE", "auto")
    initial_state: ConsultationGraphState = {
        "run_state": run_state or RunState(),
        "user_input": user_input,
        "errors": [],
        "metrics": {},
        "done": False,
        "extractor_mode_requested": requested_mode,
        "graph_runtime": "pending",
        "rag_enabled": rag_enabled,
    }

    if use_langgraph:
        compiled = build_consultation_graph()
        if compiled is not None:
            initial_state["graph_runtime"] = "langgraph"
            try:
                return _finalize_graph_state(
                    compiled.invoke(initial_state),
                    graph_runtime="langgraph",
                    extractor_mode_requested=requested_mode,
                )
            except Exception as exc:
                initial_state["errors"] = list(initial_state.get("errors") or []) + [
                    f"langgraph_runtime_failed: {exc}"
                ]

    initial_state["graph_runtime"] = "sequential_fallback"
    return _finalize_graph_state(
        _run_sequential_fallback(initial_state),
        graph_runtime="sequential_fallback",
        extractor_mode_requested=requested_mode,
    )
