import unittest

from scripts.run_p4_gate import exit_code_for_result, run_p4_gate


class P45GateTests(unittest.TestCase):
    def test_p4_gate_shape_without_nested_unittest(self) -> None:
        result = run_p4_gate(run_unittest=False)

        self.assertEqual(result["phase"], "P4.5")
        self.assertEqual(result["current_gate_phase"], "P4.5")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["api_version"], "v1")
        self.assertEqual(result["api_contract_status"], "frozen")
        self.assertFalse(result["api_response_body_changed"])
        self.assertFalse(result["sqlite_schema_changed"])
        self.assertFalse(result["diagnosis_system"])
        self.assertEqual(exit_code_for_result(result), 0)

    def test_p4_gate_includes_all_stage_checks(self) -> None:
        result = run_p4_gate(run_unittest=False)
        names = {check["name"] for check in result["checks"]}

        self.assertIn("p3_5_baseline_artifact", names)
        self.assertIn("p4_1_workflow_adapter", names)
        self.assertIn("p4_2_memory_manager", names)
        self.assertIn("p4_3_rag_boundary", names)
        self.assertIn("p4_4_tool_registry", names)
        self.assertIn("report_safety_boundary", names)


if __name__ == "__main__":
    unittest.main()

