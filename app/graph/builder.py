from __future__ import annotations

from typing import Callable

from app.graph.edges import P9_NODE_NAMES
from app.graph.nodes import (
    ask_followup,
    decide_next,
    export_result,
    extract_turn,
    generate_report,
    merge_state,
    normalize_input,
    retrieve_knowledge,
    risk_rule_check,
    safety_check,
    validate_turn,
)
from app.graph.runtime import build_langgraph_runtime
from app.graph.state import ConsultationGraphState


P9_NODE_SEQUENCE: list[tuple[str, Callable[[ConsultationGraphState], ConsultationGraphState]]] = [
    ("normalize_input", normalize_input),
    ("extract_turn", extract_turn),
    ("validate_turn", validate_turn),
    ("merge_state", merge_state),
    ("risk_rule_check", risk_rule_check),
    ("decide_next", decide_next),
    ("ask_followup", ask_followup),
    ("retrieve_knowledge", retrieve_knowledge),
    ("generate_report", generate_report),
    ("safety_check", safety_check),
    ("export_result", export_result),
]


def build_p9m1_graph():
    assert [name for name, _ in P9_NODE_SEQUENCE] == P9_NODE_NAMES
    return build_langgraph_runtime(P9_NODE_SEQUENCE)


__all__ = ["P9_NODE_SEQUENCE", "build_p9m1_graph"]
