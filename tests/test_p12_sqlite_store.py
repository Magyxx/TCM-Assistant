from __future__ import annotations

import unittest

from scripts.verify_p12_persistence import verify


class P12SQLiteStoreTests(unittest.TestCase):
    def test_sqlite_tables_cover_p12_contract(self) -> None:
        payload = verify()

        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["checks"]["sqlite_tables_cover_contract"])
        self.assertIn("sessions", payload["storage_contract"]["api_sqlite"]["tables"])
        self.assertIn("final_reports", payload["storage_contract"]["p7_sqlite"]["table_counts"])


if __name__ == "__main__":
    unittest.main()
