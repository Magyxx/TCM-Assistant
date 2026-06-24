from __future__ import annotations

from app.config.settings import AppSettings, get_settings
from app.rag.bm25_stub import search
from app.rag.evidence_pack import build_evidence_pack as build_realpath_evidence_pack
from app.rag.evidence import EvidencePack
from app.storage.models import utc_now


def _realpath_pack(query: str, *, top_k: int) -> EvidencePack:
    pack = build_realpath_evidence_pack(query, top_k=top_k)
    return EvidencePack(
        query=pack.query,
        backend="bm25_realpath",
        chunks=[
            {
                "chunk_id": chunk.chunk_id,
                "source_id": chunk.source_id,
                "title": chunk.title,
                "content": chunk.content,
                "score": chunk.score,
                "source_type": chunk.source_type,
                "trust_level": chunk.trust_level or "project_curated",
                "metadata": {
                    **chunk.metadata,
                    "risk_level": chunk.risk_level,
                    "p1_f1_realpath": True,
                },
            }
            for chunk in pack.chunks
        ],
        skipped=False,
        skip_reason="" if pack.chunks else "no_bm25_candidates",
        created_at=pack.generated_at,
    )


def retrieve_evidence_pack(
    query: str,
    *,
    top_k: int = 3,
    settings: AppSettings | None = None,
) -> EvidencePack:
    settings = settings or get_settings()
    if not settings.ENABLE_RAG:
        return EvidencePack(
            query=query,
            backend=settings.RAG_BACKEND,
            chunks=[],
            skipped=True,
            skip_reason="rag_disabled_by_config",
            created_at=utc_now(),
        )
    if settings.RAG_BACKEND == "bm25_realpath":
        try:
            return _realpath_pack(query, top_k=top_k)
        except Exception as exc:
            return EvidencePack(
                query=query,
                backend="bm25_realpath",
                chunks=[],
                skipped=True,
                skip_reason=f"bm25_realpath_failed:{exc.__class__.__name__}",
                created_at=utc_now(),
            )
    if settings.RAG_BACKEND != "bm25_stub":
        return EvidencePack(
            query=query,
            backend=settings.RAG_BACKEND,
            chunks=[],
            skipped=True,
            skip_reason=f"backend_not_available:{settings.RAG_BACKEND}",
            created_at=utc_now(),
        )
    return search(query, top_k=top_k, enabled=True)
