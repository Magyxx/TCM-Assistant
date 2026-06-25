from __future__ import annotations

import unittest

from scripts.verify_p12_api_contract import verify


class P12ApiHealthTests(unittest.TestCase):
    def test_extended_health_returns_storage_backend_matrix_and_live_skip(self) -> None:
        payload = verify()

        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["checks"]["health_returns_readiness"])
        self.assertEqual(payload["health"]["storage_status"]["default_backend"], "sqlite")
        self.assertEqual(payload["health"]["live_vllm"]["status"], "skipped")
        self.assertIn("backend_count", payload["health"]["backend_matrix_summary"])


if __name__ == "__main__":
    unittest.main()
