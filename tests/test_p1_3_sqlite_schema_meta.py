from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.api.sqlite_store import (
    STORE_SCHEMA_STAGE,
    STORE_SCHEMA_VERSION,
    SchemaVersionError,
    fetch_schema_meta,
    fetch_store_table_counts,
    initialize_database,
)


class P13SQLiteSchemaMetaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "schema_meta.sqlite3"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def test_initialize_creates_schema_meta(self) -> None:
        initialize_database(self.db_path)

        meta = fetch_schema_meta(self.db_path)
        counts = fetch_store_table_counts(self.db_path)

        self.assertEqual(meta["schema_version"], str(STORE_SCHEMA_VERSION))
        self.assertEqual(meta["schema_stage"], STORE_SCHEMA_STAGE)
        self.assertEqual(meta["store_name"], "tcm_assistant_sqlite_store")
        self.assertGreaterEqual(counts["schema_meta"], 3)
        self.assertEqual(counts["sessions"], 0)
        self.assertEqual(counts["session_states"], 0)
        self.assertEqual(counts["turns"], 0)

    def test_initialize_is_idempotent_for_schema_meta_rows(self) -> None:
        initialize_database(self.db_path)
        conn = self._connect()
        try:
            before = conn.execute(
                "SELECT key, value, updated_at FROM schema_meta ORDER BY key"
            ).fetchall()
        finally:
            conn.close()

        initialize_database(self.db_path)
        conn = self._connect()
        try:
            after = conn.execute(
                "SELECT key, value, updated_at FROM schema_meta ORDER BY key"
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual([tuple(row) for row in before], [tuple(row) for row in after])

    def test_initialize_migrates_legacy_p1_2_database_without_data_loss(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(
                """
                CREATE TABLE sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    stage TEXT,
                    mode TEXT,
                    rag_enabled INTEGER
                );
                CREATE TABLE session_states (
                    session_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    turn_index INTEGER NOT NULL,
                    user_input TEXT NOT NULL,
                    response_json TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(session_id, turn_index)
                );
                INSERT INTO sessions VALUES (
                    'legacy-session', 'created', 'updated', 'P1.2', 'fake', 1
                );
                INSERT INTO session_states VALUES (
                    'legacy-session', '{"turn_count": 0}', 'updated'
                );
                """
            )
        finally:
            conn.close()

        initialize_database(self.db_path)

        meta = fetch_schema_meta(self.db_path)
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT session_id, stage, mode FROM sessions WHERE session_id = ?",
                ("legacy-session",),
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(meta["schema_stage"], STORE_SCHEMA_STAGE)
        self.assertIsNotNone(row)
        self.assertEqual(row["stage"], "P1.2")
        self.assertEqual(row["mode"], "fake")

    def test_future_schema_version_is_rejected(self) -> None:
        initialize_database(self.db_path)
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE schema_meta SET value = ? WHERE key = 'schema_version'",
                (str(STORE_SCHEMA_VERSION + 1),),
            )
            conn.commit()
        finally:
            conn.close()

        with self.assertRaises(SchemaVersionError):
            initialize_database(self.db_path)


if __name__ == "__main__":
    unittest.main()
