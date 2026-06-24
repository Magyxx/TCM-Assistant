from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EvidenceChunk(BaseModel):
    chunk_id: str
    source_id: str
    title: str
    content: str
    score: float = 0.0
    source_type: str = "demo_knowledge"
    trust_level: str = "medium"
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidencePack(BaseModel):
    query: str
    backend: str = "bm25_stub"
    chunks: list[EvidenceChunk] = Field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""
    created_at: str


CORE_STATE_FIELDS = {"chief_complaint", "duration", "risk_status", "risk_rule_ids"}


def assert_no_core_field_overwrite(payload: dict[str, Any]) -> bool:
    return not any(key in payload for key in CORE_STATE_FIELDS)


__all__ = ["CORE_STATE_FIELDS", "EvidenceChunk", "EvidencePack", "assert_no_core_field_overwrite"]
