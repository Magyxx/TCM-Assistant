from __future__ import annotations

import unittest

from scripts.verify_p12_report_eval_api import verify


class P12ApiReportTests(unittest.TestCase):
    def test_report_endpoint_returns_ready_safe_report(self) -> None:
        payload = verify()

        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["checks"]["report_get_ready"])
        self.assertTrue(payload["checks"]["report_post_ready"])
        self.assertTrue(payload["checks"]["report_safety_contract"])


if __name__ == "__main__":
    unittest.main()
