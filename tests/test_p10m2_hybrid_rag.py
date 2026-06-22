from __future__ import annotations

from pathlib import Path

from app.rag.bm25_retriever import P10M2BM25Retriever
from app.rag.dense_retriever import P10M2DenseFallbackRetriever
from app.rag.hybrid_retriever import P10M2HybridRetriever
from app.rag.knowledge_builder import build_knowledge_chunks


def test_p10m2_knowledge_builder_and_hybrid_retriever(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "red_flags.md").write_text(
        "# Red Flags\n\n## Chest Pain\nChest pain with breathing difficulty requires urgent offline care.",
        encoding="utf-8",
    )
    chunks_path = tmp_path / "processed" / "chunks.jsonl"
    chunks = build_knowledge_chunks(raw_dir=raw_dir, chunks_path=chunks_path, include_legacy=False)

    assert chunks_path.exists()
    assert chunks[0].chunk_id
    assert chunks[0].source_type == "red_flag"

    bm25 = P10M2BM25Retriever(chunks_path, auto_build=False).retrieve("chest pain breathing difficulty", top_k=1)
    dense = P10M2DenseFallbackRetriever(chunks_path, auto_build=False).retrieve("chest pain breathing difficulty", top_k=1)
    hybrid = P10M2HybridRetriever(chunks_path=chunks_path).search("chest pain breathing difficulty", top_k=1)

    assert bm25
    assert dense
    assert hybrid["results"]
    result = hybrid["results"][0]
    assert result["bm25_score"] >= 0
    assert result["dense_score"] >= 0
    assert result["fusion_score"] >= 0
    assert result["citation_id"]

