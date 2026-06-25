from __future__ import annotations

import unittest

from scripts.verify_p12_persistence import verify


class P12AuditPersistenceTests(unittest.TestCase):
    def test_report_and_audit_events_are_persisted_without_tracked_db_files(self) -> None:
        payload = verify()

        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["checks"]["report_persisted"])
        self.assertTrue(payload["checks"]["audit_events_persisted"])
        self.assertTrue(payload["checks"]["gitignore_covers_db_files"])
        self.assertTrue(payload["checks"]["no_tracked_db_files"])


if __name__ == "__main__":
    unittest.main()
