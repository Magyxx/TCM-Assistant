from __future__ import annotations

from typing import List

from app.rag.base import BaseRetriever, EvidenceChunk


class EmbeddingRetriever(BaseRetriever):
    """
    Placeholder dense retriever interface.

    P0 intentionally does not download embedding models or require a vector DB.
    When unavailable, callers should fall back to BM25.
    """

    def __init__(self, available: bool = False) -> None:
        self.available = available

    def retrieve(self, query: str, top_k: int = 3) -> List[EvidenceChunk]:
        if not self.available:
            return []
        raise NotImplementedError("Dense retrieval is not configured in P0.")
