from __future__ import annotations

import unittest

from scripts.verify_p12_api_contract import verify


class P12ApiSessionTests(unittest.TestCase):
    def test_session_creation_and_state_read_contract(self) -> None:
        payload = verify()

        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["checks"]["create_session_returns_contract"])
        self.assertTrue(payload["checks"]["state_reads_after_turn"])
        self.assertEqual(payload["session_contract"]["extractor_mode"], "fake")


if __name__ == "__main__":
    unittest.main()
