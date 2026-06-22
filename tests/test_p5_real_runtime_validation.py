import unittest

from scripts.run_p5_real_runtime_validation import TRACE_FIELDS, run_p5_validation


class P5RealRuntimeValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_p5_validation(
            write_artifacts=False,
            probe_real_llm=False,
            real_llm_timeout_seconds=1,
        )
        cls.validation = cls.result["validation"]
        cls.traces = cls.result["trace_samples"]["traces"]

    def test_langgraph_runtime_cases_pass(self) -> None:
        runtime = self.validation["real_langgraph_runtime_status"]

        self.assertEqual(runtime["status"], "ok")
        self.assertTrue(runtime["graph_compile_ok"])
        self.assertGreaterEqual(runtime["graph_runtime_cases_passed"], 5)

    def test_trace_schema_is_complete(self) -> None:
        self.assertTrue(self.result["trace_samples"]["trace_field_completeness_pass"])
        for trace in self.traces:
            self.assertEqual(set(TRACE_FIELDS), set(trace))

    def test_p5_core_metrics_have_no_blocking_violations(self) -> None:
        metrics = self.validation["metrics_table"]

        self.assertEqual(metrics["report_safety_violation_count"], 0)
        self.assertEqual(metrics["diagnosis_or_prescription_violation_count"], 0)
        self.assertEqual(metrics["high_risk_false_negative_count"], 0)
        self.assertEqual(metrics["state_loss_rate"], 0.0)

    def test_fake_fallback_real_llm_metrics_are_separated(self) -> None:
        modes = self.validation["extractor_mode_status"]

        self.assertEqual(modes["separated_mode_names"], ["fake", "rule_fallback", "real_llm"])
        self.assertEqual(modes["mode_counts"]["fake"]["attempt_count"], 1)
        self.assertEqual(modes["mode_counts"]["rule_fallback"]["attempt_count"], 1)
        self.assertIn("attempt_count", modes["mode_counts"]["real_llm"])


if __name__ == "__main__":
    unittest.main()
