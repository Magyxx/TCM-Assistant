from __future__ import annotations

from app.rag.evidence import EvidenceChunk, EvidencePack
from app.storage.models import utc_now


STATIC_CHUNKS = [
    EvidenceChunk(
        chunk_id="safe-001",
        source_id="p1-safety",
        title="High-risk symptoms require offline care",
        content="Chest pain, breathing difficulty, altered consciousness, severe abdominal pain, and blood in stool should be handled offline by clinicians.",
        score=1.0,
        source_type="safety_policy",
        trust_level="high",
    ),
    EvidenceChunk(
        chunk_id="safe-002",
        source_id="p1-safety",
        title="Assistant boundary",
        content="The assistant organizes inquiry information and risk prompts; it must not diagnose, prescribe, or replace clinician judgment.",
        score=0.9,
        source_type="safety_policy",
        trust_level="high",
    ),
    EvidenceChunk(
        chunk_id="digest-001",
        source_id="p1-demo",
        title="Digestive discomfort inquiry",
        content="For stomach bloating, collect duration, relation to meals, pain severity, stool changes, fever, vomiting, and red-flag symptoms.",
        score=0.8,
        source_type="demo_knowledge",
        trust_level="medium",
    ),
    EvidenceChunk(
        chunk_id="sleep-001",
        source_id="p1-demo",
        title="Sleep inquiry",
        content="For sleep issues, collect duration, sleep onset, awakenings, daytime function, stress context, and urgent mental-health risk signals.",
        score=0.7,
        source_type="demo_knowledge",
        trust_level="medium",
    ),
    EvidenceChunk(
        chunk_id="privacy-001",
        source_id="p1-privacy",
        title="Privacy boundary",
        content="Raw patient identity data should not be written into reusable knowledge stores; logs should prefer redacted text and hashes.",
        score=0.7,
        source_type="privacy_policy",
        trust_level="high",
    ),
]


def search(query: str, *, top_k: int = 3, enabled: bool = True) -> EvidencePack:
    if not enabled:
        return EvidencePack(
            query=query,
            backend="bm25_stub",
            chunks=[],
            skipped=True,
            skip_reason="rag_disabled_by_config",
            created_at=utc_now(),
        )
    normalized = (query or "").lower()
    matches: list[EvidenceChunk] = []
    for chunk in STATIC_CHUNKS:
        haystack = f"{chunk.title} {chunk.content}".lower()
        if any(token and token in haystack for token in normalized.split()) or any(
            marker in query for marker in ("胃", "胀", "痛", "饭后", "睡", "胸痛", "便血")
        ):
            matches.append(chunk)
    return EvidencePack(
        query=query,
        backend="bm25_stub",
        chunks=matches[:top_k],
        skipped=False,
        skip_reason="",
        created_at=utc_now(),
    )
