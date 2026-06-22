from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path

from app.rag.bm25_retriever import p10m2_tokenize
from app.rag.chunk_schema import KnowledgeChunk
from app.rag.knowledge_builder import DEFAULT_CHUNKS_PATH, build_p10m2_knowledge, load_knowledge_chunks


def _chunks_path() -> Path:
    return Path(os.getenv("RAG_CHUNKS_PATH") or DEFAULT_CHUNKS_PATH)


def _bucket(token: str, dimensions: int) -> int:
    digest = hashlib.sha1(token.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % dimensions


def _hashed_vector(text: str, dimensions: int = 128) -> list[float]:
    vector = [0.0 for _ in range(dimensions)]
    for token in p10m2_tokenize(text):
        vector[_bucket(token, dimensions)] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


class P10M2DenseFallbackRetriever:
    def __init__(self, chunks_path: Path | None = None, *, dimensions: int = 128, auto_build: bool = True) -> None:
        self.chunks_path = chunks_path or _chunks_path()
        self.dimensions = dimensions
        self.auto_build = auto_build
        self._chunks: list[KnowledgeChunk] | None = None
        self._vectors: dict[str, list[float]] = {}

    def load_chunks(self) -> list[KnowledgeChunk]:
        if self._chunks is None:
            chunks = load_knowledge_chunks(self.chunks_path)
            if not chunks and self.auto_build:
                build_p10m2_knowledge()
                chunks = load_knowledge_chunks(self.chunks_path)
            self._chunks = chunks
            self._vectors = {
                chunk.chunk_id: _hashed_vector(
                    f"{chunk.title} {chunk.content} {' '.join(chunk.entities)}",
                    self.dimensions,
                )
                for chunk in chunks
            }
        return list(self._chunks)

    @property
    def available(self) -> bool:
        return bool(self.load_chunks())

    def score_chunks(self, query: str) -> list[tuple[KnowledgeChunk, float]]:
        chunks = self.load_chunks()
        if not chunks:
            return []
        query_vector = _hashed_vector(query, self.dimensions)
        return [
            (chunk, _cosine(query_vector, self._vectors.get(chunk.chunk_id, [])))
            for chunk in chunks
        ]

    def retrieve(self, query: str, top_k: int = 5) -> list[tuple[KnowledgeChunk, float]]:
        scored = self.score_chunks(query)
        scored.sort(key=lambda item: item[1], reverse=True)
        positive = [item for item in scored if item[1] > 0]
        return (positive or scored)[:top_k]

