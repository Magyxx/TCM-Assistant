from __future__ import annotations

from typing import Dict, List, Literal

from app.rag.base import BaseRetriever, EvidenceChunk
from app.rag.bm25_retriever import BM25Retriever
from app.rag.embedding_retriever import EmbeddingRetriever
from app.rag.reranker import NoopReranker


HybridMode = Literal["bm25_only", "dense_only", "hybrid"]


class HybridRetriever(BaseRetriever):
    def __init__(
        self,
        mode: HybridMode = "bm25_only",
        bm25_retriever: BM25Retriever | None = None,
        dense_retriever: EmbeddingRetriever | None = None,
        reranker: NoopReranker | None = None,
    ) -> None:
        self.mode = mode
        self.bm25_retriever = bm25_retriever or BM25Retriever()
        self.dense_retriever = dense_retriever or EmbeddingRetriever(available=False)
        self.reranker = reranker or NoopReranker()

    @staticmethod
    def _mark(results: List[EvidenceChunk], retriever_type: str) -> List[EvidenceChunk]:
        return [item.model_copy(update={"retriever_type": retriever_type}) for item in results]

    def retrieve(self, query: str, top_k: int = 3) -> List[EvidenceChunk]:
        if self.mode == "bm25_only":
            return self.bm25_retriever.retrieve(query, top_k=top_k)

        if self.mode == "dense_only":
            dense_results = self.dense_retriever.retrieve(query, top_k=top_k)
            if dense_results:
                return dense_results
            return self._mark(self.bm25_retriever.retrieve(query, top_k=top_k), "dense_fallback")

        dense_results = self.dense_retriever.retrieve(query, top_k=top_k)
        bm25_results = self.bm25_retriever.retrieve(query, top_k=top_k)

        if not dense_results:
            return self._mark(bm25_results, "hybrid_fallback")

        merged: Dict[str, EvidenceChunk] = {}
        for item in bm25_results + dense_results:
            existing = merged.get(item.chunk_id)
            if existing is None or item.score > existing.score:
                merged[item.chunk_id] = item

        reranked = self.reranker.rerank(query, list(merged.values()), top_k=top_k)
        return [item.model_copy(update={"retriever_type": "hybrid"}) for item in reranked]


def retrieve_evidence(query: str, top_k: int = 3, mode: HybridMode = "bm25_only") -> List[EvidenceChunk]:
    return HybridRetriever(mode=mode).retrieve(query=query, top_k=top_k)
