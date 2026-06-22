from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.storage.models import RunStateSnapshot, StorageSession, StorageTurn
from app.storage.sqlite_store import P7_TABLES, P7SQLiteStore


class P7StorageTests(unittest.TestCase):
    def test_sqlite_tables_and_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = P7SQLiteStore(Path(temp_dir) / "p7.sqlite3")
            store.create_session(StorageSession(session_id="s1", mode="fake"))
            store.append_turn_bundle(
                turn=StorageTurn(turn_id="t1", session_id="s1", turn_index=1, user_input="胃胀"),
                run_state=RunStateSnapshot(session_id="s1", turn_id="t1", state={"turn_count": 1}),
            )

            counts = store.table_counts()
            bundle = store.fetch_session_bundle("s1")

        self.assertTrue(all(table in counts for table in P7_TABLES))
        self.assertIsNotNone(bundle)
        self.assertEqual(bundle["session"]["session_id"], "s1")
        self.assertEqual(bundle["turns"][0]["turn_id"], "t1")


if __name__ == "__main__":
    unittest.main()
