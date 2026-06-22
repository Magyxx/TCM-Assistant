from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence
from uuid import uuid4

from app.observability.schemas import P7TraceEvent
from app.rag.evidence_schema import P6EvidenceChunk


P6B_RAG_TRACE_FIELDS = [
    "session_id",
    "turn_id",
    "trace_id",
    "rag_runtime_enabled",
    "rag_index_path",
    "rag_index_version",
    "chunk_schema_version",
    "source_manifest_version",
    "retrieved_evidence_count",
    "retrieved_chunk_ids",
    "retrieved_source_ids",
    "retrieval_mode",
    "fallback_used",
    "fallback_reason",
    "rag_boundary_pass",
    "latency_ms",
    "created_at",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_p6b_rag_trace(
    *,
    session_id: str | None,
    turn_id: str | None,
    trace_id: str | None,
    rag_runtime_enabled: bool,
    rag_index_path: str,
    rag_index_version: str,
    chunk_schema_version: str,
    source_manifest_version: str,
    evidence: Sequence[P6EvidenceChunk],
    retrieval_mode: str,
    fallback_used: bool,
    fallback_reason: str | None,
    rag_boundary_pass: bool,
    latency_ms: int,
) -> dict[str, Any]:
    payload = {
        "session_id": session_id or "p6b-validation",
        "turn_id": turn_id or "0",
        "trace_id": trace_id or f"p6b-{uuid4().hex[:12]}",
        "rag_runtime_enabled": bool(rag_runtime_enabled),
        "rag_index_path": rag_index_path,
        "rag_index_version": rag_index_version,
        "chunk_schema_version": chunk_schema_version,
        "source_manifest_version": source_manifest_version,
        "retrieved_evidence_count": len(evidence),
        "retrieved_chunk_ids": [item.chunk_id for item in evidence],
        "retrieved_source_ids": sorted({item.source_id for item in evidence}),
        "retrieval_mode": retrieval_mode,
        "fallback_used": bool(fallback_used),
        "fallback_reason": fallback_reason,
        "rag_boundary_pass": bool(rag_boundary_pass),
        "latency_ms": int(latency_ms),
        "created_at": utc_now(),
    }
    return {field: payload.get(field) for field in P6B_RAG_TRACE_FIELDS}


def trace_schema_pass(traces: Sequence[dict[str, Any]]) -> bool:
    return all(set(P6B_RAG_TRACE_FIELDS) == set(trace) for trace in traces)


def build_p7_trace_event(
    *,
    session_id: str,
    turn_id: str,
    api_route: str,
    run_state: Any,
    graph_output: dict[str, Any] | None = None,
    storage_write_pass: bool = True,
    memory_write_pass: bool = True,
    tool_calls: list[dict[str, Any]] | None = None,
    latency_ms: int = 0,
) -> P7TraceEvent:
    graph_output = graph_output or {}
    metadata = getattr(run_state, "metadata", {}) or {}
    p6_trace = metadata.get("p6b_rag_trace") or graph_output.get("p6b_rag_trace") or {}
    evidence = metadata.get("retrieved_evidence") or graph_output.get("retrieved_evidence") or []
    retrieved_chunk_ids = []
    for item in evidence:
        if isinstance(item, dict) and item.get("chunk_id"):
            retrieved_chunk_ids.append(str(item["chunk_id"]))
    if not retrieved_chunk_ids and isinstance(p6_trace, dict):
        retrieved_chunk_ids = [str(item) for item in p6_trace.get("retrieved_chunk_ids") or []]
    fallback_reason = metadata.get("last_error_type") or metadata.get("last_error_message_preview")
    return P7TraceEvent(
        session_id=session_id,
        turn_id=turn_id,
        trace_id=f"p7-{uuid4().hex[:12]}",
        graph_runtime=str(metadata.get("graph_runtime") or graph_output.get("graph_runtime") or "unknown"),
        api_route=api_route,
        extractor_mode=str(metadata.get("last_extractor_mode") or graph_output.get("extractor_mode") or "unknown"),
        raw_llm_json_valid=metadata.get("last_raw_llm_json_valid"),
        final_schema_pass=bool(metadata.get("last_final_schema_pass", True)),
        fallback_used=bool(metadata.get("last_fallback_used", False)),
        fallback_reason=str(fallback_reason) if fallback_reason else None,
        risk_rule_ids=list(getattr(run_state, "triggered_rule_ids", []) or []),
        risk_status=str(getattr(run_state, "risk_flags_status", "unknown")),
        retrieved_evidence_count=len(evidence) or int(p6_trace.get("retrieved_evidence_count") or 0),
        retrieved_chunk_ids=retrieved_chunk_ids,
        rag_boundary_pass=bool(p6_trace.get("rag_boundary_pass", True)),
        memory_write_pass=memory_write_pass,
        storage_write_pass=storage_write_pass,
        tool_calls=list(tool_calls or []),
        safety_rewrite_used=bool(metadata.get("safety_rewrite_used", False)),
        latency_ms=int(latency_ms),
    )


def p7_trace_schema_pass(traces: Sequence[dict[str, Any]]) -> bool:
    fields = set(P7TraceEvent.model_fields)
    return all(fields.issubset(set(trace)) for trace in traces)
