import unittest

from scripts.run_p6c_retrieval_eval import run_p6c_retrieval_eval


class P6CRetrievalEvalTests(unittest.TestCase):
    def test_expanded_retrieval_eval_meets_p6c_thresholds(self) -> None:
        payload = run_p6c_retrieval_eval(write_artifacts=False)
        metrics = payload["metrics"]

        self.assertEqual(payload["status"], "ok")
        self.assertGreaterEqual(metrics["retrieval_eval_case_count"], 30)
        self.assertGreaterEqual(metrics["retrieval_eval_pass_rate"], 0.90)
        self.assertEqual(metrics["critical_risk_retrieval_recall"], 1.0)
        self.assertEqual(metrics["negated_risk_false_positive_count"], 0)
        self.assertEqual(metrics["unapproved_source_loaded_count"], 0)
        self.assertEqual(metrics["smoke_only_source_loaded_count"], 0)
        self.assertEqual(metrics["rag_injection_followed_count"], 0)
        self.assertTrue(metrics["evidence_audit_schema_pass"])


if __name__ == "__main__":
    unittest.main()
