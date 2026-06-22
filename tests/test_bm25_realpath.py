import unittest

from app.rag import bm25_retriever
from app.rag.bm25_retriever import BM25Retriever
from app.rag.hybrid_retriever import HybridRetriever
from app.schemas.report_schemas import RunState


class BM25RealpathSmokeTests(unittest.TestCase):
    def test_bm25_realpath_returns_evidence_and_does_not_touch_core_state(self) -> None:
        state = RunState(
            chief_complaint="stomach discomfort",
            duration="two days",
            symptoms_status="none",
            risk_flags_status="none",
        )
        before = state.model_dump()

        evidence = HybridRetriever(mode="bm25_only").retrieve(
            "chief complaint stomach discomfort duration two days observe advice",
            top_k=2,
        )

        self.assertEqual(before, state.model_dump())
        self.assertTrue(evidence)
        self.assertLessEqual(len(evidence), 2)
        expected_type = "bm25" if bm25_retriever.BM25Okapi is not None else "bm25_lexical_fallback"
        self.assertIn(evidence[0].retriever_type, {expected_type, "bm25_fallback"})

    def test_p8_bm25_realpath_returns_metadata_chunks(self) -> None:
        retriever = BM25Retriever()
        results = retriever.retrieve_p8("胃胀", top_k=2)

        self.assertTrue(results)
        self.assertLessEqual(len(results), 2)
        self.assertTrue(results[0].source_id)
        self.assertTrue(results[0].chunk_id)
        self.assertIsInstance(results[0].score, float)
        self.assertTrue(results[0].content)

    def test_p8_required_queries_have_explainable_behavior(self) -> None:
        retriever = BM25Retriever()
        for query in ["胃胀", "胸痛", "便血", "没有发热", "睡眠不好"]:
            with self.subTest(query=query):
                results = retriever.retrieve_p8(query, top_k=3)
                self.assertTrue(results)
                self.assertTrue(results[0].content)
                self.assertIn(results[0].metadata["retriever_type"], {"bm25", "bm25_lexical_fallback", "bm25_fallback"})


if __name__ == "__main__":
    unittest.main()
