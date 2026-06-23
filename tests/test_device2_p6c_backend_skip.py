from __future__ import annotations

import unittest

from scripts.device2.eval_compare_backends import run_backend_compare


class Device2P6CBackendSkipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = run_backend_compare(write_artifacts=False)
        cls.metrics = {item["backend"]: item for item in cls.payload["metrics"]}

    def test_cloud_llm_missing_config_is_safe_skip(self) -> None:
        cloud = self.payload["backends"]["cloud_llm"]

        self.assertEqual(cloud["status"], "skipped")
        self.assertEqual(cloud["skip_reason"], "missing_api_key_or_offline_test")
        self.assertEqual(self.payload["status"], "ok")

    def test_skipped_backend_metrics_are_not_fabricated(self) -> None:
        cloud_metrics = self.metrics["cloud_llm"]

        self.assertEqual(cloud_metrics["case_count"], 0)
        self.assertEqual(cloud_metrics["skipped_case_count"], self.payload["case_source"]["case_count"])
        self.assertIsNone(cloud_metrics["json_valid_rate"])
        self.assertIsNone(cloud_metrics["schema_pass_rate"])
        self.assertIsNone(cloud_metrics["negation_accuracy"])
        self.assertEqual(cloud_metrics["risk_false_negative_count"], 0)

    def test_backend_skipped_badcases_are_recorded(self) -> None:
        distribution = self.payload["badcase_type_distribution"]

        self.assertEqual(distribution["backend_skipped"], self.payload["case_source"]["case_count"])

    def test_predictions_sample_has_no_weight_paths(self) -> None:
        self.assertTrue(self.payload["checks"]["predictions_sample_safe"])
        self.assertTrue(self.payload["safety"]["predictions_sample_safe"])


if __name__ == "__main__":
    unittest.main()
