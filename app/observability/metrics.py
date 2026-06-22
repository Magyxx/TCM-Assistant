from __future__ import annotations

from typing import Any, Iterable

from app.observability.schemas import P7_TRACE_FIELDS


def trace_schema_pass(events: Iterable[dict[str, Any]]) -> bool:
    expected = set(P7_TRACE_FIELDS)
    return all(expected.issubset(set(event)) for event in events)


def summarize_trace_metrics(events: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(events)
    fallback_count = sum(1 for event in events if event.get("fallback_used"))
    return {
        "trace_schema_pass": trace_schema_pass(events),
        "trace_storage_pass": total > 0,
        "trace_event_count": total,
        "fallback_used_rate": (fallback_count / total) if total else 0.0,
        "rag_boundary_pass": all(event.get("rag_boundary_pass") is True for event in events),
    }
