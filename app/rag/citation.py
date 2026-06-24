from __future__ import annotations

import re
from typing import Any

from app.rag.chunk_schema import CitationCoverage, EvidenceCitation, RetrievalResult


def _excerpt(text: str, limit: int = 180) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def citation_from_result(result: RetrievalResult) -> EvidenceCitation:
    return EvidenceCitation(
        citation_id=result.citation_id,
        chunk_id=result.chunk_id,
        source_id=result.source_id,
        title=result.title,
        trust_level=result.trust_level or "project_curated",
        content_excerpt=_excerpt(result.content),
        source_type=result.source_type,
        risk_level=result.risk_level,
    )


def citations_from_results(results: list[RetrievalResult] | list[dict[str, Any]]) -> list[EvidenceCitation]:
    citations: list[EvidenceCitation] = []
    for item in results:
        result = item if isinstance(item, RetrievalResult) else RetrievalResult.model_validate(item)
        citations.append(citation_from_result(result))
    return citations


def attach_citations_to_report(report: Any, citations: list[EvidenceCitation]) -> Any:
    payload = [citation.model_dump() for citation in citations]
    evidence_ids = [citation.citation_id for citation in citations]
    coverage = citation_coverage(
        {
            "impression": getattr(report, "impression", ""),
            "advice": getattr(report, "advice", []),
            "evidence_ids": evidence_ids,
        },
        citations,
    ).model_dump()
    if hasattr(report, "model_copy"):
        metadata = dict(getattr(report, "metadata", {}) or {})
        metadata["citation_coverage"] = coverage
        return report.model_copy(
            update={
                "evidence_citations": payload,
                "evidence_ids": evidence_ids,
                "citation_coverage": coverage,
                "metadata": metadata,
            },
            deep=True,
        )
    if isinstance(report, dict):
        updated = dict(report)
        updated["evidence_citations"] = payload
        updated["evidence_ids"] = evidence_ids
        updated["citation_coverage"] = coverage
        metadata = dict(updated.get("metadata") or {})
        metadata["citation_coverage"] = coverage
        updated["metadata"] = metadata
        return updated
    return report


def citation_coverage(report: dict[str, Any], citations: list[EvidenceCitation] | list[dict[str, Any]]) -> CitationCoverage:
    if not citations:
        return CitationCoverage(status="not_applicable")
    citation_ids = {
        citation.citation_id if isinstance(citation, EvidenceCitation) else str(citation.get("citation_id", ""))
        for citation in citations
    }
    evidence_ids = {str(item) for item in report.get("evidence_ids") or []}
    rag_sections = []
    if report.get("impression"):
        rag_sections.append("impression")
    if report.get("advice"):
        rag_sections.append("advice")
    if not rag_sections:
        return CitationCoverage(status="not_applicable")
    missing = [] if evidence_ids & citation_ids else rag_sections
    coverage = 1.0 if not missing else 0.0
    return CitationCoverage(
        status="passed" if not missing else "failed",
        cited_sentence_count=len(evidence_ids & citation_ids),
        rag_sentence_count=len(rag_sections),
        coverage=coverage,
        missing_sections=missing,
    )

