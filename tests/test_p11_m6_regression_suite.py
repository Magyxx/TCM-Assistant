from __future__ import annotations

import unittest

from scripts.verify_p11_regression_suite import verify


class P11M6RegressionSuiteTests(unittest.TestCase):
    def test_regression_suite_aggregates_existing_contracts_without_recursive_unittest(self) -> None:
        payload = verify(run_unittest=False, run_compile=False)

        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["checks"]["contract_artifacts_ok"])
        self.assertTrue(payload["checks"]["contract_verifiers_ok"])
        self.assertTrue(payload["checks"]["secret_scan_clean"])
        self.assertTrue(payload["checks"]["tracked_sensitive_files_clean"])
        self.assertTrue(payload["checks"]["protected_tag_unchanged"])
        self.assertEqual(payload["release_packaging"]["checks_total"], 12)
        self.assertEqual(payload["release_packaging"]["checks_passed"], 12)
        self.assertIn(payload["live_vllm_smoke"]["status"], {"skipped", "enabled_not_run_by_regression_aggregation"})


if __name__ == "__main__":
    unittest.main()
