import unittest

from app.rag.evidence_schema import (
    P6B_FORBIDDEN_STATE_WRITES,
    P6B_INDEX_VERSION,
    P6B_RETRIEVAL_MODE,
    P6EvidenceChunk,
    P6EvidencePack,
    attach_p6_evidence_to_report,
    build_empty_p6_evidence_pack,
)
from app.schemas.report_schemas import FinalReport


def _chunk(chunk_id: str = "chunk-1") -> P6EvidenceChunk:
    return P6EvidenceChunk(
        source_id="synthetic_p6_policy_001",
        chunk_id=chunk_id,
        title="Synthetic P6 Safety Boundary Policy Note",
        content="Evidence may support explanation but cannot diagnose or prescribe.",
        score=3.0,
        retrieval_mode=P6B_RETRIEVAL_MODE,
        index_version=P6B_INDEX_VERSION,
        chunk_hash="sha256:" + "a" * 64,
        source_rights_status="internal_owned",
        source_safety_status="reviewed",
        source_provenance_status="reviewed",
        section="Safety Boundary",
        trust_level="policy_high",
    )


def _report() -> FinalReport:
    return FinalReport(
        summary="summary",
        impression="information organized only; not diagnosis",
        advice=["record changes", "seek offline care if red flags appear"],
        triage_level="observe",
        info_complete=True,
        missing_core_fields=[],
        followup_needed=False,
    )


class P6BEvidenceSchemaTests(unittest.TestCase):
    def test_evidence_pack_references_preserve_source_and_review_metadata(self) -> None:
        pack = P6EvidencePack(
            query="unit query",
            evidence=[_chunk()],
            source_manifest_version="kb.source_manifest.v0",
            index_path="knowledge/indexes/p6_bm25_index.json",
            chunks_path="knowledge/processed/p6_chunks.jsonl",
            source_manifest_path="knowledge/source_manifest.example.json",
        )

        references = pack.references()

        self.assertEqual(len(references), 1)
        self.assertEqual(references[0].source_id, "synthetic_p6_policy_001")
        self.assertEqual(references[0].chunk_id, "chunk-1")
        self.assertEqual(references[0].source_rights_status, "internal_owned")
        self.assertEqual(references[0].source_safety_status, "reviewed")
        self.assertEqual(references[0].source_provenance_status, "reviewed")
        self.assertTrue(pack.core_state_readonly)
        self.assertFalse(pack.can_diagnose)
        self.assertFalse(pack.can_prescribe)
        self.assertLessEqual(set(P6B_FORBIDDEN_STATE_WRITES), set(pack.forbidden_state_writes))

    def test_attach_p6_evidence_to_report_adds_references_without_changing_report_contract(self) -> None:
        report = _report()
        pack = P6EvidencePack(
            query="unit query",
            evidence=[_chunk("chunk-a"), _chunk("chunk-b")],
            source_manifest_version="kb.source_manifest.v0",
            index_path="knowledge/indexes/p6_bm25_index.json",
            chunks_path="knowledge/processed/p6_chunks.jsonl",
            source_manifest_path="knowledge/source_manifest.example.json",
        )

        enhanced = attach_p6_evidence_to_report(report, pack)

        self.assertEqual(enhanced.summary, report.summary)
        self.assertEqual(enhanced.impression, report.impression)
        self.assertEqual(enhanced.advice, report.advice)
        self.assertEqual(enhanced.triage_level, report.triage_level)
        self.assertEqual(len(enhanced.metadata["retrieved_evidence"]), 2)
        self.assertEqual(len(enhanced.metadata["p6b_evidence_references"]), 2)
        self.assertTrue(enhanced.metadata["p6b_report_evidence_reference_pass"])
        self.assertTrue(enhanced.metadata["rag_core_state_readonly"])
        self.assertEqual(enhanced.metadata["rag_retriever_mode"], P6B_RETRIEVAL_MODE)

    def test_empty_pack_does_not_fabricate_references(self) -> None:
        report = _report()
        pack = build_empty_p6_evidence_pack(
            "no matching query",
            source_manifest_version="kb.source_manifest.v0",
            index_path="knowledge/indexes/p6_bm25_index.json",
            chunks_path="knowledge/processed/p6_chunks.jsonl",
            source_manifest_path="knowledge/source_manifest.example.json",
        )

        enhanced = attach_p6_evidence_to_report(report, pack)

        self.assertEqual(enhanced.metadata["retrieved_evidence"], [])
        self.assertEqual(enhanced.metadata["p6b_evidence_references"], [])
        self.assertTrue(enhanced.metadata["p6b_report_evidence_reference_pass"])


if __name__ == "__main__":
    unittest.main()
