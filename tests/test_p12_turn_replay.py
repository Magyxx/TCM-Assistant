from __future__ import annotations

import unittest

from scripts.verify_p12_persistence import verify


class P12TurnReplayTests(unittest.TestCase):
    def test_session_store_replay_uses_persisted_turns_and_state(self) -> None:
        payload = verify()

        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["checks"]["session_store_replayable"])
        self.assertGreaterEqual(payload["storage_contract"]["session_store"]["turn_count"], 2)


if __name__ == "__main__":
    unittest.main()
