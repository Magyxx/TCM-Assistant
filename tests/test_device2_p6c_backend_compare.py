from __future__ import annotations

import unittest

from scripts.device2.eval_compare_backends import run_backend_compare
from scripts.device2.verify_d2_p6c_backend_compare import build_validation_payload


class Device2P6CBackendCompareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = run_backend_compare(write_artifacts=False)
        cls.metrics = {item["backend"]: item for item in cls.payload["metrics"]}
        cls.predictions = {
            (row["backend"], row["case_id"]): row for row in cls.payload["predictions_sample"]
        }

    def test_same_eval_cases_and_fake_regression_pass(self) -> None:
        self.assertEqual(self.payload["status"], "ok")
        self.assertTrue(self.payload["checks"]["same_eval_cases_used"])
        self.assertEqual(self.payload["backends"]["fake"]["status"], "passed")
        self.assertEqual(self.metrics["fake"]["schema_pass_rate"], 1.0)

    def test_local_lora_schema_pass_is_counted(self) -> None:
        self.assertEqual(self.payload["backends"]["local_lora"]["status"], "passed")
        self.assertEqual(self.metrics["local_lora"]["json_valid_rate"], 1.0)
        self.assertEqual(self.metrics["local_lora"]["schema_pass_rate"], 1.0)
        self.assertEqual(self.metrics["local_lora"]["fallback_rate"], 0.0)

    def test_invalid_json_is_recorded_for_local_base(self) -> None:
        row = self.predictions[("local_base", "schema_fail_mock_001")]

        self.assertFalse(row["json_valid"])
        self.assertFalse(row["schema_pass"])
        self.assertIn("invalid_json", row["failure_types"])
        self.assertEqual(self.metrics["local_base"]["failure_type_counts"]["invalid_json"], 1)

    def test_schema_fail_still_blocks_runstate_write(self) -> None:
        self.assertTrue(self.payload["checks"]["schema_fail_no_runstate_write"])

    def test_local_lora_risk_status_is_rule_owned(self) -> None:
        high_risk = self.predictions[("local_lora", "high_risk_chest_dyspnea_001")]
        digestive = self.predictions[("local_lora", "digestive_negation_001")]

        self.assertEqual(high_risk["final_turn_output"]["risk_flags_status"], "present")
        self.assertTrue(high_risk["risk_owned_by_rules"])
        self.assertEqual(digestive["parsed_json"]["risk_flags_status"], "present")
        self.assertEqual(digestive["final_turn_output"]["risk_flags_status"], "none")
        self.assertTrue(digestive["lora_risk_claim_stripped"])

    def test_local_lora_vs_local_base_is_comparable(self) -> None:
        comparison = self.payload["local_lora_vs_local_base"]

        self.assertTrue(comparison["comparable"])
        self.assertIn("schema_pass_rate", comparison["improved_metrics"])
        self.assertIn("duration_match_rate", comparison["improved_metrics"])
        self.assertFalse(comparison["regressed_metrics"])

    def test_validation_payload_shape(self) -> None:
        validation = build_validation_payload(self.payload)

        self.assertEqual(validation["stage"], "D2-P6C_BACKEND_COMPARE")
        self.assertEqual(validation["status"], "ok")
        self.assertEqual(validation["checks"]["cloud_skip_safe"], "passed")
        self.assertEqual(validation["checks"]["weights_not_tracked"], "passed")


if __name__ == "__main__":
    unittest.main()
