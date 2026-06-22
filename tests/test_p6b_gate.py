import unittest

from scripts.run_p6b_gate import run_p6b_gate


class P6BGateTests(unittest.TestCase):
    def test_p6b_gate_schema_and_hard_metrics_pass_in_light_mode(self) -> None:
        payload = run_p6b_gate(
            write_artifact=False,
            run_unittest=False,
            run_compileall=False,
            run_p4_gate_check=False,
            run_p5_regression=False,
        )
        metrics = payload["metrics"]

        self.assertEqual(payload["phase"], "P6B")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["knowledge_pipeline"]["status"], "ok")
        self.assertEqual(payload["runtime_rag"]["status"], "ok")
        self.assertEqual(payload["rag_boundary"]["status"], "ok")
        self.assertEqual(payload["safety"]["status"], "ok")
        self.assertEqual(payload["trace"]["status"], "ok")
        self.assertEqual(metrics["p6_knowledge_pipeline_status"], "ok")
        self.assertGreaterEqual(metrics["approved_source_count"], 1)
        self.assertTrue(metrics["runtime_index_loaded"])
        self.assertTrue(metrics["chunk_schema_pass"])
        self.assertTrue(metrics["source_review_gate_pass"])
        self.assertGreater(metrics["retrieved_evidence_count"], 0)
        self.assertEqual(metrics["retrieval_eval_pass_rate"], 1.0)
        self.assertTrue(metrics["rag_boundary_pass"])
        self.assertEqual(metrics["core_state_mutation_count_by_rag"], 0)
        self.assertEqual(metrics["unapproved_source_loaded_count"], 0)
        self.assertEqual(metrics["smoke_only_source_loaded_count"], 0)
        self.assertTrue(metrics["report_evidence_reference_pass"])
        self.assertEqual(metrics["hallucinated_citation_count"], 0)
        self.assertEqual(metrics["high_risk_false_negative_count"], 0)
        self.assertEqual(metrics["report_safety_violation_count"], 0)
        self.assertEqual(metrics["diagnosis_or_prescription_violation_count"], 0)
        self.assertTrue(metrics["trace_schema_pass"])
        self.assertTrue(metrics["all_json_artifacts_valid"])
        self.assertFalse(payload["failure_analysis"]["blockers"])


if __name__ == "__main__":
    unittest.main()
