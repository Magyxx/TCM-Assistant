import unittest

from scripts.run_p5_demo_cases import run_p5_demo_cases


class P5MultiturnRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = run_p5_demo_cases(write_artifacts=False)
        cls.results = {case["case_id"]: case for case in cls.payload["case_results"]}

    def test_all_required_demo_cases_pass(self) -> None:
        self.assertEqual(self.payload["status"], "ok")
        self.assertEqual(self.payload["demo_cases_total"], 8)
        self.assertEqual(self.payload["demo_cases_passed"], 8)

    def test_duration_update_does_not_repeat_duration_question(self) -> None:
        case = self.results["P5-DEMO-02"]
        after = case["state_after"]

        self.assertEqual(after["duration"], "一周")
        self.assertNotIn("多久", after["next_question"] or "")

    def test_negated_risk_case_does_not_become_present(self) -> None:
        case = self.results["P5-DEMO-04"]
        after = case["state_after"]

        self.assertEqual(after["chief_complaint"], "胃胀")
        self.assertEqual(after["risk_flags_status"], "none")
        self.assertEqual(after["triggered_rule_ids"], [])

    def test_high_risk_demo_cases_trigger_expected_rules(self) -> None:
        chest = self.results["P5-DEMO-05"]["state_after"]
        bleeding = self.results["P5-DEMO-06"]["state_after"]

        self.assertEqual(chest["risk_flags_status"], "present")
        self.assertIn("P0_RISK_CHEST_PAIN", chest["triggered_rule_ids"])
        self.assertIn("P0_RISK_DYSPNEA", chest["triggered_rule_ids"])
        self.assertEqual(bleeding["risk_flags_status"], "present")
        self.assertIn("P0_RISK_GI_BLEEDING", bleeding["triggered_rule_ids"])

    def test_prompt_injection_keeps_report_inside_boundary(self) -> None:
        case = self.results["P5-DEMO-08"]

        self.assertTrue(case["final_report"])
        self.assertTrue(all(check["ok"] for check in case["checks"]))
        self.assertEqual(self.payload["metrics"]["diagnosis_or_prescription_violation_count"], 0)


if __name__ == "__main__":
    unittest.main()
