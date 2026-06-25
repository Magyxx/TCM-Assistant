from __future__ import annotations

import unittest

from scripts.verify_p12_report_eval_api import verify


class P12ApiExtendedHealthTests(unittest.TestCase):
    def test_extended_health_reports_storage_backend_p11_and_live_skip(self) -> None:
        payload = verify()

        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["checks"]["extended_health_contract"])
        self.assertEqual(payload["extended_health"]["live_vllm"]["status"], "skipped")
        self.assertEqual(payload["extended_health"]["storage_status"]["default_backend"], "sqlite")


if __name__ == "__main__":
    unittest.main()
