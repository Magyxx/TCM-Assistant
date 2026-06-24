from __future__ import annotations

from app.rag.bm25_retriever import BM25Retriever
from app.rag.document_store import LocalTextDocumentStore
from app.rag.knowledge_loader import ROOT_KNOWLEDGE_FILE, load_knowledge_chunks
from app.schemas.evidence import EvidenceChunk


def test_knowledge_loader_returns_chunks() -> None:
    chunks = load_knowledge_chunks(ROOT_KNOWLEDGE_FILE)

    assert chunks
    assert all(isinstance(chunk, EvidenceChunk) for chunk in chunks)


def test_bm25_returns_p9_evidence_chunks() -> None:
    retriever = BM25Retriever(document_store=LocalTextDocumentStore(ROOT_KNOWLEDGE_FILE))
    chunks = retriever.retrieve_p9("胃胀 饭后 食欲 大便 风险信号", top_k=3)

    assert chunks
    assert all(isinstance(chunk, EvidenceChunk) for chunk in chunks)
    assert all(chunk.chunk_id and chunk.content for chunk in chunks)
