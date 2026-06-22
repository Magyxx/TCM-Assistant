from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple, TypedDict

from app.graph.state import ConsultationGraphState


GraphNode = Callable[[ConsultationGraphState], ConsultationGraphState]
NodeSequence = List[Tuple[str, GraphNode]]


class _LangGraphEnvelope(TypedDict, total=False):
    payload: Dict[str, Any]


def is_langgraph_available() -> bool:
    try:
        import langgraph  # noqa: F401
    except Exception:
        return False
    return True


def run_fallback_runtime(
    initial_state: ConsultationGraphState,
    node_sequence: NodeSequence,
) -> ConsultationGraphState:
    state = initial_state.model_copy(deep=True)
    for _, node_func in node_sequence:
        state = node_func(state)
    state.graph_runtime = "sequential_fallback"
    return state


def build_langgraph_runtime(node_sequence: NodeSequence) -> Any:
    try:
        from langgraph.graph import END, StateGraph
    except Exception:
        return None

    graph = StateGraph(_LangGraphEnvelope)

    def wrap(node_func: GraphNode) -> Callable[[_LangGraphEnvelope], _LangGraphEnvelope]:
        def invoke(envelope: _LangGraphEnvelope) -> _LangGraphEnvelope:
            state = ConsultationGraphState.model_validate(envelope.get("payload") or {})
            return {"payload": node_func(state).model_dump()}

        return invoke

    for node_name, node_func in node_sequence:
        graph.add_node(node_name, wrap(node_func))

    graph.set_entry_point(node_sequence[0][0])
    for (current_name, _), (next_name, _) in zip(node_sequence, node_sequence[1:]):
        graph.add_edge(current_name, next_name)
    graph.add_edge(node_sequence[-1][0], END)
    return graph.compile()


def run_langgraph_runtime(
    initial_state: ConsultationGraphState,
    node_sequence: NodeSequence,
) -> ConsultationGraphState:
    compiled = build_langgraph_runtime(node_sequence)
    if compiled is None:
        raise RuntimeError("langgraph_unavailable")
    result = compiled.invoke({"payload": initial_state.model_dump()})
    state = ConsultationGraphState.model_validate(result.get("payload") or {})
    state.graph_runtime = "langgraph"
    return state
