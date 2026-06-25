from __future__ import annotations

import unittest

from scripts.verify_p12_report_eval_api import verify


class P12ApiEvalTests(unittest.TestCase):
    def test_eval_final_route_supports_lightweight_smoke_without_live_model(self) -> None:
        payload = verify()

        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["checks"]["eval_final_lightweight_smoke"])
        self.assertFalse(payload["eval_contract"]["requires_live_model"])


if __name__ == "__main__":
    unittest.main()
