import unittest

import app.chains.rag_enhancer as rag_enhancer
from app.rag import bm25_retriever
from app.rag.hybrid_retriever import HybridRetriever
from app.schemas.report_schemas import FinalReport, RunState


def sample_state() -> RunState:
    return RunState(
        chief_complaint="腹泻",
        duration="两天",
        symptoms_status="none",
        risk_flags_status="none",
    )


def sample_report() -> FinalReport:
    return FinalReport(
        summary="主诉：腹泻\n持续时间：两天",
        impression="当前信息用于问诊整理。",
        advice=["记录症状变化。"],
        triage_level="observe",
        info_complete=True,
        missing_core_fields=[],
        followup_needed=False,
    )


class P0HybridRagTest(unittest.TestCase):
    def test_rank_bm25_missing_fallback_does_not_crash(self):
        original = bm25_retriever.BM25Okapi
        bm25_retriever.BM25Okapi = None
        try:
            evidence = HybridRetriever(mode="bm25_only").retrieve("主诉：腹泻；观察建议", top_k=2)
        finally:
            bm25_retriever.BM25Okapi = original

        self.assertEqual(len(evidence), 2)
        self.assertEqual(evidence[0].retriever_type, "bm25_lexical_fallback")

    def test_evidence_metadata_is_complete(self):
        evidence = HybridRetriever(mode="hybrid").retrieve("主诉：腹泻；风险状态：none", top_k=2)

        self.assertLessEqual(len(evidence), 2)
        self.assertTrue(evidence)
        for item in evidence:
            self.assertTrue(item.chunk_id)
            self.assertTrue(item.source)
            self.assertTrue(item.content)
            self.assertIsInstance(item.score, float)
            self.assertTrue(item.retriever_type)

    def test_real_bm25_path_reports_bm25_when_available(self):
        evidence = HybridRetriever(mode="bm25_only").retrieve("主诉：腹泻；观察建议", top_k=2)

        self.assertTrue(evidence)
        if bm25_retriever.BM25Okapi is not None:
            self.assertEqual(evidence[0].retriever_type, "bm25")

    def test_hybrid_without_dense_marks_fallback(self):
        evidence = HybridRetriever(mode="hybrid").retrieve("主诉：腹泻；观察建议", top_k=2)

        self.assertTrue(evidence)
        self.assertEqual(evidence[0].retriever_type, "hybrid_fallback")

    def test_rag_enhancer_does_not_modify_core_report_fields(self):
        state = sample_state()
        report = sample_report()

        enhanced = rag_enhancer.enhance_final_report_with_rag(state, report, use_llm=False)

        self.assertEqual(enhanced.triage_level, report.triage_level)
        self.assertEqual(enhanced.info_complete, report.info_complete)
        self.assertEqual(enhanced.missing_core_fields, report.missing_core_fields)
        self.assertEqual(enhanced.followup_needed, report.followup_needed)
        self.assertIn("retrieved_evidence", enhanced.metadata)

    def test_no_evidence_does_not_crash(self):
        original = rag_enhancer.retrieve_evidence
        rag_enhancer.retrieve_evidence = lambda *args, **kwargs: []
        try:
            enhanced = rag_enhancer.enhance_final_report_with_rag(sample_state(), sample_report(), use_llm=False)
        finally:
            rag_enhancer.retrieve_evidence = original

        self.assertEqual(enhanced.metadata["retrieved_evidence"], [])
        self.assertFalse(enhanced.metadata["rag_llm_used"])


if __name__ == "__main__":
    unittest.main()
