from __future__ import annotations

import unittest

from scripts.verify_p12_persistence import verify


class P12SessionPersistenceTests(unittest.TestCase):
    def test_session_turn_and_state_are_persisted(self) -> None:
        payload = verify()

        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["checks"]["session_created"])
        self.assertTrue(payload["checks"]["turn_persisted"])
        self.assertTrue(payload["checks"]["state_snapshot_restored"])


if __name__ == "__main__":
    unittest.main()
