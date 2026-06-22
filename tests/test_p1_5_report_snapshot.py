from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.session_runtime import clear_session_cache, clear_sessions
from app.api.sqlite_store import (
    fetch_store_table_counts,
    initialize_database,
)


COMPLETE_FAKE_INPUT = (
    "\u80c3\u80c0\u4e24\u5929\uff0c"
    "\u6ca1\u6709\u5176\u4ed6\u75c7\u72b6\uff0c"
    "\u4e5f\u6ca1\u6709\u80f8\u75db"
)

TURN_KEYS = {
    "session_id",
    "turn_id",
    "turn_count",
    "next_question",
    "state",
    "risk_flags_status",
    "risk_rule_ids",
    "risk_reasons",
    "final_report",
    "metadata",
    "safety_disclaimer",
}

REPORT_KEYS = {
    "session_id",
    "ready",
    "final_report",
    "missing_core_fields",
    "next_question",
    "safety_disclaimer",
}


class P15ReportSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "p1_5.sqlite3"
        self.previous_db_path = os.environ.get("TCM_API_DB_PATH")
        os.environ["TCM_API_DB_PATH"] = str(self.db_path)
        clear_sessions()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        clear_sessions()
        if self.previous_db_path is None:
            os.environ.pop("TCM_API_DB_PATH", None)
        else:
            os.environ["TCM_API_DB_PATH"] = self.previous_db_path
        self.temp_dir.cleanup()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _create_session(self) -> dict:
        response = self.client.post(
            "/sessions",
            json={"extractor_mode": "fake", "rag_enabled": True},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _submit_complete_turn(self, session_id: str, user_input: str = COMPLETE_FAKE_INPUT) -> dict:
        response = self.client.post(
            f"/sessions/{session_id}/turn",
            json={"user_input": user_input},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _state_json(self, session_id: str) -> dict:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT state_json FROM session_states WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        return json.loads(row["state_json"])

    def _report_rows(self, session_id: str) -> list[sqlite3.Row]:
        conn = self._connect()
        try:
            return conn.execute(
                """
                SELECT report_id, session_id, state_version, report_json,
                       created_at, safety_flags_json
                FROM reports
                WHERE session_id = ?
                ORDER BY created_at ASC, report_id ASC
                """,
                (session_id,),
            ).fetchall()
        finally:
            conn.close()

    def test_reports_table_exists_after_init(self) -> None:
        initialize_database(self.db_path)
        counts = fetch_store_table_counts(self.db_path)

        self.assertIn("reports", counts)
        self.assertEqual(counts["reports"], 0)

    def test_legacy_database_auto_migrates_reports_table(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy.sqlite3"
        conn = sqlite3.connect(legacy_path)
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

        initialize_database(legacy_path)
        conn = sqlite3.connect(legacy_path)
        try:
            report_count = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
            session_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(report_count, 0)
        self.assertEqual(session_count, 1)

    def test_state_version_increments_on_successful_turns(self) -> None:
        session = self._create_session()

        self.assertEqual(self._state_json(session["session_id"])["state_version"], 0)
        self._submit_complete_turn(session["session_id"])
        self.assertEqual(self._state_json(session["session_id"])["state_version"], 1)
        self._submit_complete_turn(session["session_id"])
        self.assertEqual(self._state_json(session["session_id"])["state_version"], 2)

    def test_cache_clear_recovers_state_version(self) -> None:
        session = self._create_session()
        self._submit_complete_turn(session["session_id"])
        self._submit_complete_turn(session["session_id"])

        clear_session_cache()
        response = self.client.get(f"/sessions/{session['session_id']}/state")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["turn_count"], 2)
        self.assertEqual(payload["state"]["state_version"], 2)

    def test_report_generation_creates_snapshot_with_fields(self) -> None:
        session = self._create_session()
        response = self._submit_complete_turn(session["session_id"])

        self.assertIsInstance(response["final_report"], dict)
        rows = self._report_rows(session["session_id"])
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertTrue(row["report_id"])
        self.assertEqual(row["session_id"], session["session_id"])
        self.assertEqual(row["state_version"], 1)
        report_json = json.loads(row["report_json"])
        safety_flags = json.loads(row["safety_flags_json"])
        self.assertIn("summary", report_json)
        self.assertTrue(safety_flags["passed"])
        self.assertEqual(safety_flags["flags"], [])

    def test_report_snapshot_is_redacted(self) -> None:
        session = self._create_session()
        secret = "sk-" + "snapshotsecret1234567890"
        self._submit_complete_turn(
            session["session_id"],
            f"{COMPLETE_FAKE_INPUT} OPENAI_API_KEY={secret}",
        )

        candidates = [
            self.db_path,
            self.db_path.with_name(f"{self.db_path.name}-wal"),
            self.db_path.with_name(f"{self.db_path.name}-shm"),
        ]
        persisted = b"".join(path.read_bytes() for path in candidates if path.exists())
        decoded = persisted.decode("utf-8", errors="ignore")
        self.assertNotIn(secret, decoded)
        self.assertNotIn("OPENAI_API_KEY", decoded)

    def test_api_response_top_level_contract_is_unchanged(self) -> None:
        session = self._create_session()
        turn = self._submit_complete_turn(session["session_id"])
        report_response = self.client.get(f"/sessions/{session['session_id']}/report")

        self.assertEqual(set(turn.keys()), TURN_KEYS)
        self.assertIn("state_version", turn["state"])
        self.assertEqual(report_response.status_code, 200)
        report = report_response.json()
        self.assertEqual(set(report.keys()), REPORT_KEYS)
        self.assertTrue(report["ready"])

    def test_repeated_report_generation_saves_multiple_snapshots(self) -> None:
        session = self._create_session()
        self._submit_complete_turn(session["session_id"])
        self._submit_complete_turn(session["session_id"])

        rows = self._report_rows(session["session_id"])
        self.assertEqual(len(rows), 2)
        self.assertEqual([row["state_version"] for row in rows], [1, 2])

    def test_audit_session_script_outputs_summary_without_raw_text(self) -> None:
        session = self._create_session()
        self._submit_complete_turn(session["session_id"])
        project_root = Path(__file__).resolve().parents[1]

        result = subprocess.run(
            [
                sys.executable,
                "scripts/audit_session.py",
                "--db",
                str(self.db_path),
                "--session",
                session["session_id"],
                "--json",
            ],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)

        self.assertTrue(payload["passed"])
        self.assertTrue(payload["session_exists"])
        self.assertEqual(payload["turn_count"], 1)
        self.assertEqual(payload["current_state_version"], 1)
        self.assertEqual(payload["report_count"], 1)
        self.assertFalse(payload["secret_found"])
        self.assertFalse(payload["raw_user_text_included"])
        self.assertNotIn(COMPLETE_FAKE_INPUT, result.stdout)

    def test_migration_is_idempotent(self) -> None:
        initialize_database(self.db_path)
        initialize_database(self.db_path)
        before = fetch_store_table_counts(self.db_path)
        initialize_database(self.db_path)
        after = fetch_store_table_counts(self.db_path)

        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
