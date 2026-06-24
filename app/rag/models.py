from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.storage.models import utc_now


RetrievalMode = Literal["bm25"]
GuardStatus = Literal["passed", "skipped", "failed"]


class EvidenceChunk(BaseModel):
    chunk_id: str
    source_id: str
    title: str = ""
    content: str
    score: float
    source_type: str = "local_text"
    trust_level: str | None = None
    risk_level: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidencePack(BaseModel):
    query: str
    normalized_query: str
    chunks: list[EvidenceChunk] = Field(default_factory=list)
    retrieval_mode: RetrievalMode = "bm25"
    top_k: int = 3
    generated_at: str = Field(default_factory=utc_now)
    guard_status: GuardStatus = "passed"
    notes: list[str] = Field(default_factory=list)

    @property
    def result_count(self) -> int:
        return len(self.chunks)
