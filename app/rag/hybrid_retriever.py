from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Literal

from app.rag.base import BaseRetriever, EvidenceChunk
from app.rag.bm25_retriever import BM25Retriever, P10M2BM25Retriever
from app.rag.chunk_schema import EvidenceCitation, RetrievalResult
from app.rag.citation import citations_from_results
from app.rag.dense_retriever import P10M2DenseFallbackRetriever
from app.rag.embedding_retriever import EmbeddingRetriever
from app.rag.knowledge_builder import DEFAULT_CHUNKS_PATH
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


P10M2RetrievalMode = Literal["bm25", "dense", "hybrid"]


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


class P10M2HybridRetriever:
    def __init__(
        self,
        *,
        chunks_path: Path | None = None,
        bm25_weight: float | None = None,
        dense_weight: float | None = None,
        rrf_k: int = 60,
    ) -> None:
        chunks_path = chunks_path or Path(os.getenv("RAG_CHUNKS_PATH") or DEFAULT_CHUNKS_PATH)
        self.bm25 = P10M2BM25Retriever(chunks_path)
        self.dense = P10M2DenseFallbackRetriever(chunks_path)
        self.bm25_weight = bm25_weight if bm25_weight is not None else _float_env("RAG_BM25_WEIGHT", 0.55)
        self.dense_weight = dense_weight if dense_weight is not None else _float_env("RAG_DENSE_WEIGHT", 0.45)
        self.rrf_k = rrf_k

    @staticmethod
    def _normalize(scores: dict[str, float]) -> dict[str, float]:
        if not scores:
            return {}
        maximum = max(scores.values()) or 0.0
        if maximum <= 0:
            return {key: 0.0 for key in scores}
        return {key: value / maximum for key, value in scores.items()}

    @staticmethod
    def _rank_map(scored: list[tuple[str, float]]) -> dict[str, int]:
        return {chunk_id: rank for rank, (chunk_id, _score) in enumerate(scored, start=1)}

    def search(self, query: str, *, top_k: int = 5, mode: P10M2RetrievalMode = "hybrid") -> dict[str, object]:
        top_k = max(1, min(int(top_k or 5), 20))
        bm25_raw = self.bm25.retrieve(query, top_k=max(top_k, 20))
        dense_raw = self.dense.retrieve(query, top_k=max(top_k, 20))
        chunk_by_id = {chunk.chunk_id: chunk for chunk, _score in bm25_raw + dense_raw}

        bm25_scores = {chunk.chunk_id: float(score) for chunk, score in bm25_raw}
        dense_scores = {chunk.chunk_id: float(score) for chunk, score in dense_raw}
        bm25_norm = self._normalize(bm25_scores)
        dense_norm = self._normalize(dense_scores)

        if mode == "bm25":
            candidate_ids = set(bm25_scores)
        elif mode == "dense":
            candidate_ids = set(dense_scores)
        else:
            candidate_ids = set(bm25_scores) | set(dense_scores)

        bm25_rank = self._rank_map(sorted(bm25_scores.items(), key=lambda item: item[1], reverse=True))
        dense_rank = self._rank_map(sorted(dense_scores.items(), key=lambda item: item[1], reverse=True))
        fused: list[tuple[str, float]] = []
        for chunk_id in candidate_ids:
            weighted = self.bm25_weight * bm25_norm.get(chunk_id, 0.0) + self.dense_weight * dense_norm.get(chunk_id, 0.0)
            rrf = 0.0
            if chunk_id in bm25_rank:
                rrf += 1.0 / (self.rrf_k + bm25_rank[chunk_id])
            if chunk_id in dense_rank:
                rrf += 1.0 / (self.rrf_k + dense_rank[chunk_id])
            fused.append((chunk_id, weighted + rrf))
        fused.sort(key=lambda item: item[1], reverse=True)

        results: list[RetrievalResult] = []
        for rank, (chunk_id, fusion_score) in enumerate(fused[:top_k], start=1):
            chunk = chunk_by_id[chunk_id]
            results.append(
                RetrievalResult.from_chunk(
                    chunk,
                    rank=rank,
                    bm25_score=bm25_scores.get(chunk_id, 0.0),
                    dense_score=dense_scores.get(chunk_id, 0.0),
                    fusion_score=fusion_score,
                )
            )

        citations: list[EvidenceCitation] = citations_from_results(results)
        return {
            "results": [item.model_dump() for item in results],
            "retrieval_mode": mode,
            "score_breakdown": {
                "bm25_weight": self.bm25_weight,
                "dense_weight": self.dense_weight,
                "rrf_k": self.rrf_k,
                "bm25_available": bool(bm25_raw),
                "dense_available": bool(dense_raw),
            },
            "citations": [item.model_dump() for item in citations],
        }


def retrieve_p10m2(
    query: str,
    *,
    top_k: int = 5,
    mode: P10M2RetrievalMode = "hybrid",
) -> dict[str, object]:
    return P10M2HybridRetriever().search(query, top_k=top_k, mode=mode)
