from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.storage.models import utc_now


class P7TraceEvent(BaseModel):
    session_id: str
    turn_id: str
    trace_id: str
    graph_runtime: str
    api_route: str
    extractor_mode: str
    raw_llm_json_valid: Optional[bool] = None
    final_schema_pass: bool
    fallback_used: bool
    fallback_reason: Optional[str] = None
    risk_rule_ids: List[str] = Field(default_factory=list)
    risk_status: str = "unknown"
    retrieved_evidence_count: int = 0
    retrieved_chunk_ids: List[str] = Field(default_factory=list)
    rag_boundary_pass: bool = True
    memory_write_pass: bool = True
    storage_write_pass: bool = True
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    safety_rewrite_used: bool = False
    latency_ms: int = 0
    created_at: str = Field(default_factory=utc_now)


P7_TRACE_FIELDS = tuple(P7TraceEvent.model_fields)
