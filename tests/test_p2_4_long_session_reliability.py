from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts.run_long_session_demo import LONG_SESSION_SECRET, run_long_session_demo


ROOT_DIR = Path(__file__).resolve().parents[1]
CASE_DIR = ROOT_DIR / "artifacts" / "eval_cases"


def _extract_json(stdout: str) -> dict[str, Any]:
    start = stdout.find("{")
    if start < 0:
        raise AssertionError(f"stdout did not contain JSON: {stdout!r}")
    payload, _ = json.JSONDecoder().raw_decode(stdout[start:])
    if not isinstance(payload, dict):
        raise AssertionError("stdout JSON is not an object")
    return payload


def _run_command(command: list[str], *, timeout: int = 240) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        command,
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=timeout,
    )


def _db_bytes(db_path: Path) -> bytes:
    return b"".join(
        path.read_bytes()
        for path in [
            db_path,
            db_path.with_name(f"{db_path.name}-wal"),
            db_path.with_name(f"{db_path.name}-shm"),
        ]
        if path.exists()
    )


class P24LongSessionReliabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _run_demo(self, *, turns: int, sessions: int, name: str) -> tuple[Path, dict[str, Any]]:
        db_path = self.temp_root / f"{name}.sqlite3"
        result = run_long_session_demo(
            turns=turns,
            sessions=sessions,
            db_path=db_path,
            db_mode="test",
        )
        self.assertEqual(result["status"], "ok", result)
        return db_path, result

    def test_single_session_50_turns_state_version_monotonic(self) -> None:
        db_path, result = self._run_demo(turns=50, sessions=1, name="single_50")
        item = result["results"][0]

        self.assertEqual(item["turn_count"], 50)
        self.assertEqual(item["state_version"], 50)
        self.assertTrue(item["state_version_monotonic"])
        self.assertGreaterEqual(item["report_count"], 1)
        self.assertTrue(item["state_validation_passed"])
        self.assertTrue(item["report_validation_passed"])
        self.assertTrue(item["recovered_after_cache_clear"])
        self.assertFalse(result["secret_found"])
        self.assertGreater(result["db"]["size_bytes"], 0)
        self.assertTrue(result["db"]["size_sanity_passed"])
        self.assertNotIn(LONG_SESSION_SECRET.encode("utf-8"), _db_bytes(db_path))
        self.assertNotIn(b"OPENAI_API_KEY", _db_bytes(db_path))

    def test_multi_session_interleaved_writes_are_isolated(self) -> None:
        _, result = self._run_demo(turns=8, sessions=3, name="multi_8")
        session_ids = [item["session_id"] for item in result["results"]]

        self.assertEqual(len(session_ids), 3)
        self.assertEqual(len(set(session_ids)), 3)
        for item in result["results"]:
            self.assertEqual(item["turn_count"], 8)
            self.assertEqual(item["state_version"], 8)
            self.assertGreaterEqual(item["report_count"], 1)
            self.assertTrue(item["state_validation_passed"])
            self.assertTrue(item["report_validation_passed"])
            self.assertTrue(item["recovered_after_cache_clear"])

    def test_inspect_and_audit_summarize_long_session_db(self) -> None:
        db_path, result = self._run_demo(turns=10, sessions=2, name="inspect_audit")
        first_session = result["results"][0]["session_id"]

        inspect = _run_command(
            [
                sys.executable,
                "scripts/inspect_sqlite_store.py",
                "--db",
                str(db_path),
                "--json",
            ]
        )
        audit = _run_command(
            [
                sys.executable,
                "scripts/audit_session.py",
                "--db",
                str(db_path),
                "--session",
                first_session,
                "--check-state",
                "--json",
            ]
        )
        inspect_payload = json.loads(inspect.stdout)
        audit_payload = json.loads(audit.stdout)

        self.assertEqual(inspect.returncode, 0, inspect.stderr)
        self.assertEqual(audit.returncode, 0, audit.stderr)
        self.assertEqual(inspect_payload["summary"]["session_count"], 2)
        self.assertEqual(inspect_payload["summary"]["turn_count"], 20)
        self.assertGreaterEqual(inspect_payload["summary"]["report_count"], 2)
        self.assertTrue(audit_payload["passed"])
        self.assertEqual(audit_payload["turn_count"], 10)
        self.assertEqual(audit_payload["current_state_version"], 10)
        self.assertEqual(audit_payload["database_summary"]["session_count"], 2)
        self.assertFalse(audit_payload["secret_found"])
        self.assertNotIn(LONG_SESSION_SECRET, inspect.stdout + audit.stdout)
        self.assertNotIn("OPENAI_API_KEY", inspect.stdout + audit.stdout)

    def test_run_long_session_demo_cli_json_structure_is_stable(self) -> None:
        db_path = self.temp_root / "cli.sqlite3"
        output_path = self.temp_root / "cli_result.json"
        completed = _run_command(
            [
                sys.executable,
                "scripts/run_long_session_demo.py",
                "--turns",
                "5",
                "--sessions",
                "2",
                "--db",
                str(db_path),
                "--output",
                str(output_path),
                "--json",
            ]
        )
        payload = _extract_json(completed.stdout)
        artifact = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(set(payload.keys()), set(artifact.keys()))
        self.assertEqual(payload["phase"], "P2.4")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["sessions"], 2)
        self.assertEqual(payload["turns_per_session"], 5)
        self.assertIn("checks", payload)
        self.assertIn("results", payload)
        self.assertIn("db", payload)
        self.assertFalse(payload["secret_found"])

    def test_p2_1_case_corpus_eval_still_passes_smoke(self) -> None:
        output_path = self.temp_root / "case_eval.json"
        completed = _run_command(
            [
                sys.executable,
                "scripts/run_case_corpus_eval.py",
                str(CASE_DIR),
                "--case",
                "basic_sleep_issue",
                "--output",
                str(output_path),
                "--json",
            ]
        )
        payload = _extract_json(completed.stdout)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["state_validation"]["passed"])
        self.assertTrue(payload["report_validation"]["passed"])

    def test_p1_gate_script_accepts_existing_cli_flags(self) -> None:
        completed = _run_command([sys.executable, "scripts/run_p1_gate.py", "--help"])

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--output", completed.stdout)
        self.assertIn("--skip-demo", completed.stdout)


if __name__ == "__main__":
    unittest.main()
