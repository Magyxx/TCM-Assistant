from __future__ import annotations

import unittest

from scripts.verify_p12_service_regression import verify


class P12ServiceRegressionTests(unittest.TestCase):
    def test_p12_service_regression_gate_is_green(self) -> None:
        payload = verify(check_old_artifact_churn=False)

        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["checks"]["p12_m1_to_m4_artifacts_ok"])
        self.assertTrue(payload["checks"]["p11_regression_status_ok"])
        self.assertTrue(payload["checks"]["secret_scan_clean"])
        self.assertTrue(payload["checks"]["release_packaging_12_of_12"])
        self.assertTrue(payload["checks"]["no_tracked_env_db_or_model_files"])
        self.assertTrue(payload["checks"]["no_old_artifact_churn"])

    def test_next_readiness_is_p13(self) -> None:
        payload = verify(check_old_artifact_churn=False)

        self.assertEqual(payload["next_readiness"]["recommended_phase"], "P13")
        self.assertEqual(payload["live_vllm_smoke"]["status"], "skipped")


if __name__ == "__main__":
    unittest.main()
