from __future__ import annotations

from app.rag.bm25_retriever import BM25Retriever, BM25Okapi
from app.rag.models import EvidencePack
from app.rag.query_builder import normalize_query
from app.rag.rag_guard import guard_evidence_pack


def build_evidence_pack(
    query: str,
    *,
    top_k: int = 3,
    retriever: BM25Retriever | None = None,
) -> EvidencePack:
    retriever = retriever or BM25Retriever()
    chunks = retriever.retrieve_p8(query, top_k=top_k)
    notes: list[str] = []
    if BM25Okapi is None:
        notes.append("rank_bm25_unavailable_used_lexical_fallback")
    if not chunks:
        notes.append("no_bm25_candidates")
    pack = EvidencePack(
        query=query,
        normalized_query=normalize_query(query),
        chunks=chunks,
        retrieval_mode="bm25",
        top_k=top_k,
        notes=notes,
    )
    return guard_evidence_pack(pack)
