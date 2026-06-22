from __future__ import annotations

from typing import Iterable

from app.memory.schemas import L2StructuredFact, L3CaseSummary


REQUIRED_FIELDS = ("chief_complaint", "duration", "symptoms_status", "risk_flags_status")


def summarize_from_facts(facts: Iterable[L2StructuredFact]) -> L3CaseSummary:
    fact_list = list(facts)
    by_field = {fact.field_name: fact.value for fact in fact_list}
    missing = [field for field in REQUIRED_FIELDS if field not in by_field]
    parts = []
    if "chief_complaint" in by_field:
        parts.append(f"chief_complaint={by_field['chief_complaint']}")
    if "duration" in by_field:
        parts.append(f"duration={by_field['duration']}")
    if "symptoms_status" in by_field:
        parts.append(f"symptoms_status={by_field['symptoms_status']}")
    risk_status = str(by_field.get("risk_flags_status", "unknown"))
    parts.append(f"risk_status={risk_status}")
    return L3CaseSummary(
        summary="; ".join(parts),
        missing_fields=missing,
        risk_status=risk_status,
        generated_from_fact_count=len(fact_list),
    )
