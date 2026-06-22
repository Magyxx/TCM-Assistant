from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


class StorageSession(BaseModel):
    session_id: str
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    mode: str = "fake"
    rag_enabled: bool = True
    status: Literal["active", "closed"] = "active"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StorageTurn(BaseModel):
    turn_id: str
    session_id: str
    turn_index: int
    user_input: str
    turn_output: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)


class RunStateSnapshot(BaseModel):
    snapshot_id: str = Field(default_factory=lambda: new_id("state"))
    session_id: str
    turn_id: str
    state: Dict[str, Any]
    created_at: str = Field(default_factory=utc_now)


class FinalReportRecord(BaseModel):
    report_id: str = Field(default_factory=lambda: new_id("report"))
    session_id: str
    turn_id: str
    report: Dict[str, Any]
    safety_check: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)


class RiskEventRecord(BaseModel):
    event_id: str = Field(default_factory=lambda: new_id("risk"))
    session_id: str
    turn_id: str
    risk_status: str
    rule_ids: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now)


class RagEvidenceRecord(BaseModel):
    evidence_id: str = Field(default_factory=lambda: new_id("evidence"))
    session_id: str
    turn_id: str
    source_id: str
    chunk_id: str
    chunk_hash: str
    index_version: str
    score: float = 0.0
    retrieval_mode: str
    used_in_report_section: Optional[str] = None
    is_used: bool = False
    evidence: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)


class AuditLogRecord(BaseModel):
    audit_id: str = Field(default_factory=lambda: new_id("audit"))
    session_id: Optional[str] = None
    turn_id: Optional[str] = None
    event_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)


class EvalRunRecord(BaseModel):
    eval_id: str = Field(default_factory=lambda: new_id("eval"))
    status: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)


class TraceEventRecord(BaseModel):
    trace_event_id: str = Field(default_factory=lambda: new_id("trace-event"))
    session_id: str
    turn_id: str
    trace_id: str
    event: Dict[str, Any]
    created_at: str = Field(default_factory=utc_now)


class MemorySnapshotRecord(BaseModel):
    snapshot_id: str = Field(default_factory=lambda: new_id("memory"))
    session_id: str
    turn_id: str
    snapshot: Dict[str, Any]
    created_at: str = Field(default_factory=utc_now)
