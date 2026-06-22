from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EvidenceChunk(BaseModel):
    chunk_id: str
    title: str = ""
    source: str = ""
    content: str
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = ["EvidenceChunk"]
