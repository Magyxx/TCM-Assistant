from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.session_runtime import clear_session_cache, clear_sessions
from app.api.state_validator import (
    validate_session_consistency,
    validate_state,
    validate_state_json,
)
from app.schemas.report_schemas import RunState


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


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
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
        timeout=180,
    )


def _valid_state() -> dict[str, Any]:
    state = RunState().model_dump()
    state["state_version"] = 0
    return state


class P22StateValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "p2_2.sqlite3"
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

    def _create_session(self) -> str:
        response = self.client.post(
            "/sessions",
            json={"extractor_mode": "fake", "rag_enabled": True},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return str(response.json()["session_id"])

    def _submit(self, session_id: str, text: str) -> dict[str, Any]:
        response = self.client.post(
            f"/sessions/{session_id}/turn",
            json={"user_input": text},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _complete_session(self) -> str:
        session_id = self._create_session()
        self._submit(session_id, "最近胃胀")
        self._submit(session_id, "持续两天，没有其他症状")
        self._submit(session_id, "没有胸痛，也没有呼吸困难")
        return session_id

    def test_validate_state_accepts_current_run_state(self) -> None:
        result = validate_state(_valid_state())

        self.assertTrue(result["passed"], result)
        self.assertTrue(result["checks"]["required_fields"])
        self.assertTrue(result["checks"]["field_types"])

    def test_validate_state_rejects_none(self) -> None:
        result = validate_state(None)

        self.assertFalse(result["passed"])
        self.assertEqual(result["errors"][0]["code"], "state_none")

    def test_validate_state_rejects_malformed_dict(self) -> None:
        result = validate_state({"turn_count": "bad"})

        self.assertFalse(result["passed"])
        codes = {error["code"] for error in result["errors"]}
        self.assertIn("required_fields_missing", codes)
        self.assertIn("field_type_invalid", codes)

    def test_validate_state_json_rejects_corrupted_json(self) -> None:
        result = validate_state_json("{bad")

        self.assertFalse(result["passed"])
        self.assertEqual(result["errors"][0]["code"], "state_json_corrupted")

    def test_validate_state_rejects_secret_content(self) -> None:
        state = _valid_state()
        state["summary"] = "credential sk-testsecret-p2-validator-0001"

        result = validate_state(state)

        self.assertFalse(result["passed"])
        self.assertIn("secret_found", {error["code"] for error in result["errors"]})
        self.assertNotIn("sk-testsecret-p2-validator-0001", json.dumps(result, ensure_ascii=False))

    def test_validate_state_rejects_forbidden_medical_output(self) -> None:
        state = _valid_state()
        state["summary"] = "诊断为某病，并给出处方和治疗方案"

        result = validate_state(state)

        self.assertFalse(result["passed"])
        self.assertIn("forbidden_medical_output", {error["code"] for error in result["errors"]})

    def test_state_version_must_be_non_negative_integer(self) -> None:
        state = _valid_state()
        state["state_version"] = -1

        result = validate_state(state)

        self.assertFalse(result["passed"])
        self.assertIn("state_version_invalid", {error["code"] for error in result["errors"]})

    def test_multiturn_state_version_is_consistent(self) -> None:
        session_id = self._complete_session()

        result = validate_session_consistency(self.db_path, session_id)

        self.assertTrue(result["passed"], result)
        self.assertEqual(result["turn_count"], 3)
        self.assertEqual(result["state_version"], 3)
        self.assertTrue(result["checks"]["state_version_monotonic"])

    def test_cache_clear_recovers_state_version(self) -> None:
        session_id = self._complete_session()

        clear_session_cache()
        response = self.client.get(f"/sessions/{session_id}/state")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"]["state_version"], 3)
        result = validate_session_consistency(self.db_path, session_id)
        self.assertTrue(result["passed"], result)

    def test_audit_session_check_state_outputs_state_validation(self) -> None:
        session_id = self._complete_session()

        result = _run_command(
            [
                sys.executable,
                "scripts/audit_session.py",
                "--db",
                str(self.db_path),
                "--session",
                session_id,
                "--check-state",
                "--json",
            ]
        )

        payload = _extract_json(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("state_validation", payload)
        self.assertTrue(payload["state_validation"]["passed"])
        self.assertNotIn(str(self.db_path.resolve()), result.stdout)

    def test_run_case_corpus_eval_outputs_state_validation(self) -> None:
        output_path = Path(self.temp_dir.name) / "p2_eval.json"
        result = _run_command(
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

        payload = _extract_json(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("state_validation", payload)
        self.assertTrue(payload["state_validation"]["passed"])
        self.assertIn("state_validation", payload["cases"][0])
        self.assertTrue(payload["cases"][0]["state_validation"]["passed"])

    def test_p2_1_case_corpus_eval_still_passes(self) -> None:
        output_path = Path(self.temp_dir.name) / "p2_eval.json"
        result = _run_command(
            [
                sys.executable,
                "scripts/run_case_corpus_eval.py",
                str(CASE_DIR),
                "--case",
                "secret_injection_input",
                "--output",
                str(output_path),
                "--json",
            ]
        )

        payload = _extract_json(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "ok")
        self.assertFalse(payload["secret_scan"]["secret_found"])
        self.assertTrue(payload["state_validation"]["passed"])


if __name__ == "__main__":
    unittest.main()
