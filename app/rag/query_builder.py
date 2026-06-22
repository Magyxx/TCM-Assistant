from __future__ import annotations

from typing import Any, Mapping

from app.memory.models import ConsultationMemory
from app.schemas.report_schemas import RunState


HIGH_RISK_TERMS = (
    "胸痛",
    "呼吸困难",
    "便血",
    "高热",
    "意识异常",
    "剧烈腹痛",
    "chest pain",
    "dyspnea",
    "bloody stool",
    "high fever",
    "confusion",
    "severe abdominal pain",
)


def _coerce_memory(memory: ConsultationMemory | Mapping[str, Any] | None) -> ConsultationMemory | None:
    if memory is None:
        return None
    if isinstance(memory, ConsultationMemory):
        return memory
    return ConsultationMemory.model_validate(memory)


def _append(parts: list[str], label: str, value: Any) -> None:
    if value in (None, "", [], {}, "unknown"):
        return
    if isinstance(value, list):
        value = " | ".join(str(item) for item in value if item not in (None, ""))
    if value:
        parts.append(f"{label}: {value}")


def build_rag_query(
    run_state: RunState,
    *,
    memory: ConsultationMemory | Mapping[str, Any] | None = None,
) -> str:
    parts: list[str] = []
    _append(parts, "chief_complaint", run_state.chief_complaint)
    _append(parts, "duration", run_state.duration)
    _append(parts, "symptoms", run_state.symptoms)
    _append(parts, "symptoms_status", run_state.symptoms_status)
    _append(parts, "sleep", run_state.sleep)
    _append(parts, "appetite", run_state.appetite)
    _append(parts, "stool_urine", run_state.stool_urine)
    _append(parts, "risk_flags", run_state.risk_flags)
    _append(parts, "risk_status", run_state.risk_flags_status)
    _append(parts, "risk_reasons", run_state.risk_reasons)

    memory_obj = _coerce_memory(memory)
    if memory_obj is not None:
        for fact in memory_obj.facts.values():
            if fact.explicit_negation and fact.raw_text:
                parts.append(f"explicit_negation: {fact.raw_text}")

    combined = "；".join(parts)
    for term in HIGH_RISK_TERMS:
        if term in combined and f"risk_keyword: {term}" not in parts:
            parts.append(f"risk_keyword: {term}")

    parts.append("retrieve: observation advice risk warning offline care evidence")
    return "；".join(parts)


def normalize_query(query: str) -> str:
    return " ".join(query.strip().lower().split())
