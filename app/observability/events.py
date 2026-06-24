from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


FORBIDDEN_LOG_KEYS = ("api_key", "authorization", "openai_api_key", "OPENAI_API_KEY", "Authorization")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def redacted_input_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


class GraphEvent(BaseModel):
    trace_id: str = Field(default_factory=lambda: f"trace-{uuid4().hex[:12]}")
    session_id: str
    turn_id: str
    node: str
    graph_runtime: str = "unknown"
    extractor_mode: str = "unknown"
    raw_llm_json_valid: bool | None = None
    final_schema_pass: bool | None = None
    fallback_used: bool = False
    risk_rule_ids: list[str] = Field(default_factory=list)
    retrieved_evidence_count: int = 0
    safety_rewrite_used: bool = False
    latency_ms: int = 0
    timestamp: str = Field(default_factory=utc_now)
    input_length: int = 0
    redacted_input_hash: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


def generate_trace_id(prefix: str = "trace") -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


class TraceEvent(BaseModel):
    trace_id: str = Field(default_factory=generate_trace_id)
    session_id: str = ""
    turn_id: str = ""
    event_type: str
    component: str
    status: str = "ok"
    latency_ms: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=utc_now)


def sanitize_event(payload: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in payload.items():
        if any(marker.lower() in str(key).lower() for marker in FORBIDDEN_LOG_KEYS):
            safe[key] = "[redacted]"
        elif isinstance(value, dict):
            safe[key] = sanitize_event(value)
        elif isinstance(value, list):
            safe[key] = [sanitize_event(item) if isinstance(item, dict) else item for item in value]
        elif isinstance(value, str) and ("sk-" in value or "Authorization" in value or "OPENAI_API_KEY" in value):
            safe[key] = "[redacted]"
        else:
            safe[key] = value
    return safe
