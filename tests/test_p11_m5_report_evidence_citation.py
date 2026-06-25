from __future__ import annotations

import unittest

from app.rag.chunk_schema import RetrievalResult
from app.rag.citation import attach_citations_to_report, citation_coverage, citations_from_results
from app.safety.report_safety import safety_post_check_report
from app.schemas.report_schemas import FinalReport


class P11M5EvidenceCitationTests(unittest.TestCase):
    def test_evidence_citations_survive_final_report_safety_check(self) -> None:
        retrieval_result = RetrievalResult(
            chunk_id="chunk-1",
            source_id="safety_boundaries",
            title="Safety boundaries",
            content="Evidence can support explanation but cannot diagnose or prescribe.",
            score=1.0,
            fusion_score=1.0,
            citation_id="EV001",
            source_type="safety_boundary",
            trust_level="project_curated",
        )
        citations = citations_from_results([retrieval_result])
        report = FinalReport(
            summary="Structured intake summary.",
            impression="Inquiry support only.",
            advice=["Use cited safety boundaries."],
            triage_level="followup",
            info_complete=True,
            missing_core_fields=[],
            followup_needed=False,
        )

        cited_report = attach_citations_to_report(report, citations)
        checked = safety_post_check_report(cited_report).report

        self.assertEqual(checked.evidence_ids, ["EV001"])
        self.assertEqual(checked.evidence_citations[0]["chunk_id"], "chunk-1")
        self.assertEqual(checked.citation_coverage["status"], "passed")
        self.assertEqual(citation_coverage(checked.model_dump(), citations).status, "passed")
        self.assertIn("citation_coverage", checked.metadata)
        self.assertIn("safety_boundary", checked.metadata)


if __name__ == "__main__":
    unittest.main()
