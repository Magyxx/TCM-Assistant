from __future__ import annotations

from typing import Any, Iterable, List

from app.memory.schemas import L2StructuredFact
from app.schemas.report_schemas import RunState


CORE_FACT_FIELDS = (
    "chief_complaint",
    "duration",
    "symptoms",
    "symptoms_status",
    "sleep",
    "appetite",
    "stool_urine",
)
RISK_FACT_FIELDS = (
    "risk_flags",
    "risk_flags_status",
    "risk_reasons",
    "triggered_rule_ids",
)


def _has_value(value: Any) -> bool:
    return value not in (None, "", [], {}, "unknown")


def _source_span(value: Any, user_input: str) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return value if value in user_input else None


def facts_from_run_state(run_state: RunState, *, turn_id: str, user_input: str) -> List[L2StructuredFact]:
    facts: list[L2StructuredFact] = []
    for field in CORE_FACT_FIELDS:
        value = getattr(run_state, field)
        if _has_value(value):
            facts.append(
                L2StructuredFact(
                    field_name=field,
                    value=value,
                    source_turn_id=turn_id,
                    source_text_span=_source_span(value, user_input),
                    confidence=1.0,
                    source_kind="validated_schema",
                )
            )
    for field in RISK_FACT_FIELDS:
        value = getattr(run_state, field)
        if _has_value(value):
            facts.append(
                L2StructuredFact(
                    field_name=field,
                    value=value,
                    source_turn_id=turn_id,
                    source_text_span=None,
                    confidence=1.0,
                    source_kind="risk_rule_engine",
                )
            )
    return facts


def source_traceability_pass(facts: Iterable[L2StructuredFact]) -> bool:
    return all(bool(fact.source_turn_id) for fact in facts)
