from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


SourceType = Literal[
    "inquiry_guidance",
    "red_flag",
    "safety_boundary",
    "terminology",
    "legacy_knowledge",
]


class KnowledgeChunk(BaseModel):
    chunk_id: str
    source_id: str
    source_type: SourceType | str
    title: str
    content: str
    entities: list[str] = Field(default_factory=list)
    risk_level: str = "low"
    trust_level: str = "project_curated"
    version: str = "p10m2.chunk.v1"
    section: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceCitation(BaseModel):
    citation_id: str
    chunk_id: str
    source_id: str
    title: str
    trust_level: str
    content_excerpt: str
    source_type: str = ""
    risk_level: str = ""


class RetrievalResult(BaseModel):
    chunk_id: str
    source_id: str
    title: str
    content: str
    score: float
    bm25_score: float = 0.0
    dense_score: float = 0.0
    fusion_score: float = 0.0
    citation_id: str
    source_type: str = ""
    trust_level: str = ""
    risk_level: str = ""
    entities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_chunk(
        cls,
        chunk: KnowledgeChunk,
        *,
        rank: int,
        bm25_score: float = 0.0,
        dense_score: float = 0.0,
        fusion_score: float = 0.0,
    ) -> "RetrievalResult":
        score = fusion_score if fusion_score else max(bm25_score, dense_score)
        return cls(
            chunk_id=chunk.chunk_id,
            source_id=chunk.source_id,
            title=chunk.title,
            content=chunk.content,
            score=float(score),
            bm25_score=float(bm25_score),
            dense_score=float(dense_score),
            fusion_score=float(fusion_score or score),
            citation_id=f"EV{rank:03d}",
            source_type=str(chunk.source_type),
            trust_level=chunk.trust_level,
            risk_level=chunk.risk_level,
            entities=list(chunk.entities),
            metadata=dict(chunk.metadata),
        )


class CitationCoverage(BaseModel):
    status: Literal["passed", "failed", "not_applicable"]
    cited_sentence_count: int = 0
    rag_sentence_count: int = 0
    coverage: float = 0.0
    missing_sections: list[str] = Field(default_factory=list)

