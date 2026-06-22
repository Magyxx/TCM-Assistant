import unittest

from scripts.run_p5_real_runtime_validation import (
    run_bm25_rag_smoke,
    run_rag_boundary_validation,
)


class P5RagBoundaryTests(unittest.TestCase):
    def test_bm25_smoke_retrieves_evidence_without_state_write(self) -> None:
        result = run_bm25_rag_smoke()

        self.assertEqual(result["status"], "ok")
        self.assertGreater(result["evidence_count"], 0)
        self.assertEqual(result["core_state_before"], result["core_state_after"])
        self.assertIn("risk_status", result["boundary"]["forbidden_state_writes"])
        self.assertIn("risk_rule_ids", result["boundary"]["forbidden_state_writes"])
        self.assertFalse(result["boundary"]["can_diagnose"])
        self.assertFalse(result["boundary"]["can_prescribe"])

    def test_rag_boundary_preserves_core_report_fields(self) -> None:
        result = run_rag_boundary_validation()

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["core_state_unchanged"])
        self.assertTrue(result["report_contract_fields_unchanged"])
        self.assertIn("p4_rag_evidence_pack", result["metadata_added"])


if __name__ == "__main__":
    unittest.main()
