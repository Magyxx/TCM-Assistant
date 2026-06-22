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
from app.api.report_audit import audit_report
from app.api.report_validator import (
    assert_report_valid,
    validate_report,
    validate_report_snapshot,
)
from app.api.session_runtime import clear_sessions
from app.api.sqlite_store import fetch_reports_for_session
from app.api.state_validator import validate_state
from app.schemas.report_schemas import RunState


ROOT_DIR = Path(__file__).resolve().parents[1]
CASE_DIR = ROOT_DIR / "artifacts" / "eval_cases"
RUNNER = ROOT_DIR / "scripts" / "run_case_corpus_eval.py"
BOUNDARY = (
    "\u672c\u7cfb\u7edf\u4e0d\u662f\u8bca\u65ad\uff0c"
    "\u4ec5\u7528\u4e8e\u95ee\u8bca\u4fe1\u606f\u6574\u7406\uff0c"
    "\u4e0d\u80fd\u66ff\u4ee3\u533b\u751f\u5224\u65ad\u3002"
)
COMPLETE_FAKE_INPUT = (
    "\u80c3\u80c0\u4e24\u5929\uff0c"
    "\u6ca1\u6709\u5176\u4ed6\u75c7\u72b6\uff0c"
    "\u4e5f\u6ca1\u6709\u80f8\u75db"
)
REPORT_SECRET = "sk-" + "reportsecret-p2-case-0001"


def _extract_json(stdout: str) -> dict[str, Any]:
    start = stdout.find("{")
    if start < 0:
        raise AssertionError(f"stdout did not contain JSON: {stdout!r}")
    payload, _ = json.JSONDecoder().raw_decode(stdout[start:])
    if not isinstance(payload, dict):
        raise AssertionError("runner JSON output is not an object")
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


def _run_runner(args: list[str]) -> subprocess.CompletedProcess[str]:
    return _run_command([sys.executable, str(RUNNER), *args])


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


def _complete_state() -> dict[str, Any]:
    state = RunState(
        chief_complaint="\u80c3\u80c0",
        duration="\u4e24\u5929",
        symptoms_status="none",
        risk_flags_status="none",
        turn_count=3,
    ).model_dump()
    state["state_version"] = 3
    return state


def _incomplete_state() -> dict[str, Any]:
    state = RunState(
        chief_complaint="\u80c3\u80c0",
        symptoms_status="unknown",
        risk_flags_status="unknown",
        turn_count=1,
    ).model_dump()
    state["state_version"] = 1
    return state


def _urgent_state() -> dict[str, Any]:
    state = RunState(
        chief_complaint="\u8179\u75db",
        risk_flags=["\u7a81\u53d1\u5267\u70c8\u8179\u75db"],
        risk_flags_status="present",
        risk_reasons=["risk"],
        triggered_rule_ids=["P0_RISK_SEVERE_ABDOMINAL_PAIN"],
        turn_count=1,
    ).model_dump()
    state["state_version"] = 1
    return state


def _safe_report(**overrides: Any) -> dict[str, Any]:
    report: dict[str, Any] = {
        "summary": "\u4e3b\u8bc9\uff1a\u80c3\u80c0",
        "impression": f"\u5f53\u524d\u4fe1\u606f\u4ec5\u7528\u4e8e\u95ee\u8bca\u6574\u7406\u3002{BOUNDARY}",
        "advice": ["\u5efa\u8bae\u8bb0\u5f55\u75c7\u72b6\u53d8\u5316\u3002", BOUNDARY],
        "triage_level": "observe",
        "info_complete": True,
        "missing_core_fields": [],
        "followup_needed": False,
        "metadata": {},
    }
    report.update(overrides)
    return report


class P23ReportValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "p2_3.sqlite3"
        self.previous_db_path = os.environ.get("TCM_API_DB_PATH")
        os.environ["TCM_API_DB_PATH"] = str(self.db_path)
        clear_sessions()
        self.client = TestClient(app, raise_server_exceptions=False)

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

    def test_validate_report_accepts_current_generated_report_and_snapshot(self) -> None:
        session_id = self._create_session()
        response = self._submit(session_id, COMPLETE_FAKE_INPUT)
        final_report = response["final_report"]
        state = response["state"]

        result = validate_report(final_report, state)
        rows = fetch_reports_for_session(session_id, db_path=self.db_path)
        snapshot_result = validate_report_snapshot(rows[-1], state)
        flags = rows[-1]["safety_flags_json"]

        self.assertTrue(result["passed"], result)
        assert_report_valid(final_report, state)
        self.assertTrue(snapshot_result["passed"], snapshot_result)
        self.assertTrue(snapshot_result["snapshot"]["stored_validator_present"])
        self.assertTrue(flags["passed"])
        self.assertTrue(flags["validator"]["passed"])
        self.assertIn("no_secret", flags["validator"]["checks"])

    def test_none_and_empty_reports_fail_clearly(self) -> None:
        for report in [None, "", [], {}]:
            with self.subTest(report=report):
                result = validate_report(report, _complete_state())
                self.assertFalse(result["passed"])
                self.assertTrue(result["errors"])

    def test_forbidden_phrases_fail_named_checks(self) -> None:
        result = validate_report(
            _safe_report(impression=f"\u8bca\u65ad\u4e3a\u67d0\u75c5\u3002{BOUNDARY}"),
            _complete_state(),
        )

        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["no_diagnosis"])

    def test_drug_dose_fails_safety_audit(self) -> None:
        result = validate_report(
            _safe_report(advice=["\u963f\u83ab\u897f\u6797 500mg \u6bcf\u65e5\u4e24\u6b21\u3002", BOUNDARY]),
            _complete_state(),
        )
        codes = {flag["code"] for flag in result["audit"]["flags"]}

        self.assertFalse(result["passed"])
        self.assertIn("drug_dose_like", codes)

    def test_secret_report_fails_and_output_is_redacted(self) -> None:
        secret = "sk-" + "validatorsecret1234567890"
        result = validate_report(
            _safe_report(advice=[f"OPENAI_API_KEY={secret}", BOUNDARY]),
            _complete_state(),
        )
        serialized = json.dumps(result, ensure_ascii=False)

        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["no_secret"])
        self.assertNotIn(secret, serialized)
        self.assertNotIn("OPENAI_API_KEY", serialized)

    def test_dict_list_and_string_reports_are_supported(self) -> None:
        self.assertTrue(validate_report(_safe_report(), _complete_state())["passed"])
        self.assertTrue(validate_report([BOUNDARY, "\u8bb0\u5f55\u75c7\u72b6\u53d8\u5316"], _complete_state())["passed"])
        self.assertTrue(validate_report(f"\u95ee\u8bca\u4fe1\u606f\u6574\u7406\u3002{BOUNDARY}", _complete_state())["passed"])

    def test_low_info_report_claiming_complete_is_rejected(self) -> None:
        result = validate_report(_safe_report(), _incomplete_state())
        codes = {error["code"] for error in result["errors"]}

        self.assertFalse(result["passed"])
        self.assertIn("low_info_claims_complete", codes)

    def test_red_flag_cannot_be_weakened(self) -> None:
        weakened = validate_report(_safe_report(), _urgent_state())
        urgent_report = _safe_report(
            triage_level="urgent_visit",
            info_complete=False,
            missing_core_fields=["duration", "symptoms_status"],
            followup_needed=True,
            impression=f"\u5f53\u524d\u5df2\u51fa\u73b0\u9700\u8981\u8b66\u60d5\u7684\u98ce\u9669\u4fe1\u53f7\uff0c\u5efa\u8bae\u53ca\u65f6\u5c31\u533b\u3002{BOUNDARY}",
        )

        self.assertFalse(weakened["passed"])
        self.assertIn("red_flag_weakened", {error["code"] for error in weakened["errors"]})
        self.assertTrue(validate_report(urgent_report, _urgent_state())["passed"])

    def test_case_eval_outputs_report_validation(self) -> None:
        output_path = Path(self.temp_dir.name) / "result.json"
        result = _run_runner(
            [
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
        self.assertTrue(payload["report_validation"]["passed"])
        self.assertEqual(payload["metrics"]["report_validation_pass_rate"], 1.0)
        self.assertTrue(payload["cases"][0]["report_validation"]["passed"])

    def test_low_info_case_does_not_fabricate_report(self) -> None:
        result = _run_runner(
            [
                str(CASE_DIR),
                "--case",
                "report_low_info_case",
                "--output",
                str(Path(self.temp_dir.name) / "low_info.json"),
                "--json",
            ]
        )
        payload = _extract_json(result.stdout)
        case = payload["cases"][0]

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(case["report_available"])
        self.assertTrue(case["report_validation"]["passed"])
        self.assertTrue(case["report_validation"]["skipped"])

    def test_red_flag_case_report_validation_passes(self) -> None:
        result = _run_runner(
            [
                str(CASE_DIR),
                "--case",
                "report_red_flag_case",
                "--output",
                str(Path(self.temp_dir.name) / "red_flag.json"),
                "--json",
            ]
        )
        payload = _extract_json(result.stdout)
        case = payload["cases"][0]

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(case["risk_flags_status"], "present")
        self.assertTrue(case["report_validation"]["passed"])

    def test_secret_injection_case_does_not_leak_report_secret(self) -> None:
        db_path = Path(self.temp_dir.name) / "secret_case.sqlite3"
        result = _run_runner(
            [
                str(CASE_DIR),
                "--case",
                "report_secret_injection_case",
                "--db",
                str(db_path),
                "--output",
                str(Path(self.temp_dir.name) / "secret.json"),
                "--json",
            ]
        )
        payload = _extract_json(result.stdout)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(payload["cases"][0]["report_validation"]["passed"])
        self.assertFalse(payload["secret_scan"]["secret_found"])
        self.assertNotIn(REPORT_SECRET, result.stdout)
        self.assertNotIn(REPORT_SECRET, result.stderr)
        self.assertNotIn(REPORT_SECRET.encode("utf-8"), _db_bytes(db_path))

    def test_existing_p1_5_audit_and_p2_2_state_validator_still_work(self) -> None:
        audit = audit_report(_safe_report(), _complete_state())
        state_result = validate_state(RunState().model_dump() | {"state_version": 0})

        self.assertTrue(audit["passed"], audit)
        self.assertEqual(audit["flags"], [])
        self.assertTrue(state_result["passed"], state_result)


if __name__ == "__main__":
    unittest.main()
