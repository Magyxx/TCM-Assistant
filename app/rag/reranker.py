from __future__ import annotations

from typing import List

from app.rag.base import EvidenceChunk


class NoopReranker:
    def rerank(self, query: str, chunks: List[EvidenceChunk], top_k: int = 3) -> List[EvidenceChunk]:
        return sorted(chunks, key=lambda item: item.score, reverse=True)[:top_k]
