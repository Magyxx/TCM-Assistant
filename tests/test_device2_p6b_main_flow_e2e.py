from __future__ import annotations

import unittest

from scripts.device2.verify_d2_p6b_e2e import run_validation


class Device2P6BMainFlowE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = run_validation()
        cls.cases = {case["case_id"]: case for case in cls.payload["cases"]}

    def test_main_flow_selects_local_lora_through_router(self) -> None:
        digestive = self.cases["digestive_negation_001"]

        self.assertEqual(self.payload["checks"]["router_selected_local_lora"], "passed")
        self.assertEqual(digestive["backend"], "local_lora")
        self.assertEqual(digestive["strategy"], "extractor_backend_router")

    def test_schema_pass_updates_run_state(self) -> None:
        digestive = self.cases["digestive_negation_001"]
        state = digestive["run_state"]

        self.assertTrue(digestive["json_valid"])
        self.assertTrue(digestive["schema_pass"])
        self.assertTrue(digestive["run_state_updated"])
        self.assertEqual(state["chief_complaint"], "胃胀")
        self.assertEqual(state["duration"], "一周")

    def test_lora_risk_claim_is_stripped_and_rules_own_final_status(self) -> None:
        digestive = self.cases["digestive_negation_001"]
        cough = self.cases["cough_negation_001"]
        high_risk = self.cases["high_risk_chest_dyspnea_001"]

        self.assertTrue(digestive["model_claimed_risk"])
        self.assertTrue(digestive["lora_risk_claim_stripped"])
        self.assertEqual(digestive["run_state"]["risk_flags_status"], "none")
        self.assertEqual(cough["run_state"]["risk_flags_status"], "none")
        self.assertEqual(high_risk["run_state"]["risk_flags_status"], "present")
        self.assertEqual(high_risk["risk_rule_eval"]["risk_status"], "present")
        self.assertTrue(high_risk["risk_owned_by_rules"])

    def test_schema_fail_blocks_run_state_write(self) -> None:
        schema_fail = self.cases["schema_fail_001"]

        self.assertFalse(schema_fail["json_valid"])
        self.assertFalse(schema_fail["schema_pass"])
        self.assertIsNone(schema_fail["turn_output"])
        self.assertTrue(schema_fail["state_merge_blocked"])
        self.assertFalse(schema_fail["run_state_updated"])
        self.assertEqual(schema_fail["core_state_before"], schema_fail["core_state_after"])

    def test_fake_backend_regression_passes(self) -> None:
        fake = self.cases["fake_backend_regression_001"]

        self.assertEqual(self.payload["checks"]["fake_backend_regression"], "passed")
        self.assertEqual(fake["backend"], "fake")
        self.assertTrue(fake["schema_pass"])
        self.assertTrue(fake["run_state_updated"])

    def test_live_smoke_skip_has_clear_reason(self) -> None:
        live = self.payload["live_vllm"]

        if live["enabled"]:
            self.assertIn(live["status"], {"passed", "failed"})
        else:
            self.assertEqual(live["status"], "skipped")
            self.assertEqual(live["reason"], "RUN_LOCAL_VLLM_SMOKE not enabled")


if __name__ == "__main__":
    unittest.main()
