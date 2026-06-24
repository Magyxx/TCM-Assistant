from __future__ import annotations

from app.rag.citation import attach_citations_to_report, citation_coverage, citations_from_results
from app.rag.chunk_schema import RetrievalResult
from app.schemas.report_schemas import FinalReport


def test_p10m2_citations_attach_to_final_report() -> None:
    result = RetrievalResult(
        chunk_id="chunk-1",
        source_id="safety_boundaries",
        title="Safety Boundaries",
        content="RAG evidence may support explanation but cannot diagnose or prescribe.",
        score=1.0,
        fusion_score=1.0,
        citation_id="EV001",
        trust_level="project_curated",
    )
    citations = citations_from_results([result])
    report = FinalReport(
        summary="Structured intake summary.",
        impression="Inquiry support only.",
        advice=["Use cited safety boundaries."],
        triage_level="followup",
        info_complete=True,
        followup_needed=False,
    )
    updated = attach_citations_to_report(report, citations)

    assert updated.evidence_ids == ["EV001"]
    assert updated.evidence_citations[0]["chunk_id"] == "chunk-1"
    assert citation_coverage(updated.model_dump(), citations).status == "passed"

