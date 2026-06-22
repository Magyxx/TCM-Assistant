from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.run_p3_gate import (
    default_check_specs,
    exit_code_for_result,
    run_p3_gate,
    summarize_p3_gate,
    write_json,
)


def _check(name: str, code: str) -> dict[str, object]:
    return {
        "name": name,
        "command": [sys.executable, "-c", code],
        "timeout_seconds": 30,
    }


class P35RcGateTests(unittest.TestCase):
    def test_default_check_specs_cover_final_rc_gate(self) -> None:
        names = [spec["name"] for spec in default_check_specs()]

        self.assertEqual(
            names,
            [
                "p1_gate",
                "p2_gate",
                "runtime_config_check",
                "observability_check",
                "release_packaging_check",
                "api_contract_check",
                "case_corpus_eval",
                "long_session_reliability",
                "secret_scan",
                "git_diff_check",
                "unittest_discover",
            ],
        )

    def test_skip_long_session_removes_only_long_session_check(self) -> None:
        names = [spec["name"] for spec in default_check_specs(skip_long_session=True)]

        self.assertNotIn("long_session_reliability", names)
        self.assertEqual(len(names), 10)
        self.assertIn("unittest_discover", names)

    def test_single_fake_check_success_sets_p3_5_ok(self) -> None:
        result = run_p3_gate(check_specs=[_check("fake_success", "print('ok')")])

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["stage"], "P3.5")
        self.assertEqual(result["current_gate_phase"], "P3.5")
        self.assertEqual(result["recommend_next"], "P4.0")
        self.assertEqual(result["checks_passed"], 1)
        self.assertEqual(result["api_version"], "v1")
        self.assertEqual(result["api_contract_status"], "frozen")
        self.assertFalse(result["breaking_change_detected"])
        self.assertFalse(result["diagnosis_system"])
        self.assertEqual(result["boundary_violations"], [])
        self.assertEqual(exit_code_for_result(result), 0)

    def test_single_fake_check_failure_sets_status_failed(self) -> None:
        result = run_p3_gate(
            check_specs=[
                _check("fake_failure", "import sys; sys.stderr.write('bad\\n'); sys.exit(7)")
            ]
        )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["recommend_next"], "hold")
        self.assertEqual(result["checks_failed"], 1)
        self.assertEqual(result["checks"][0]["return_code"], 7)
        self.assertEqual(exit_code_for_result(result), 1)

    def test_fail_fast_stops_after_first_failure(self) -> None:
        result = run_p3_gate(
            check_specs=[
                _check("first_failure", "import sys; sys.exit(2)"),
                _check("should_not_run", "print('unexpected')"),
            ],
            fail_fast=True,
        )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["checks_total"], 1)
        self.assertEqual(result["checks"][0]["name"], "first_failure")

    def test_summary_shape_contains_required_rc_sections(self) -> None:
        result = summarize_p3_gate(
            [
                {
                    "name": "fake",
                    "command": "python -c pass",
                    "status": "ok",
                    "return_code": 0,
                    "duration_seconds": 0.0,
                    "stdout_tail": "",
                    "stderr_tail": "",
                }
            ]
        )

        for key in [
            "p1_gate",
            "p2_gate",
            "runtime_config",
            "observability",
            "release_packaging",
            "api_contract",
            "case_corpus",
            "long_session",
            "secret_scan",
        ]:
            self.assertIn(key, result)
        self.assertFalse(result["contract_changed"])
        self.assertFalse(result["api_response_body_changed"])
        self.assertFalse(result["sqlite_schema_changed"])

    def test_stdout_and_stderr_tails_are_redacted(self) -> None:
        secret = "sk-" + "p35gatefake1234567890"
        result = run_p3_gate(
            check_specs=[
                _check(
                    "redaction",
                    (
                        "import sys; "
                        f"print('OPENAI_API_KEY={secret}'); "
                        f"sys.stderr.write('TOKEN={secret}\\n')"
                    ),
                )
            ]
        )
        serialized = json.dumps(result, ensure_ascii=False)

        self.assertEqual(result["status"], "ok")
        self.assertNotIn(secret, serialized)
        self.assertNotIn("OPENAI_API_KEY", serialized)
        self.assertNotIn("TOKEN=", serialized)
        self.assertIn("[redacted-secret]", serialized)

    def test_artifact_writer_preserves_schema_and_redacts(self) -> None:
        result = run_p3_gate(check_specs=[_check("fake_success", "print('ok')")])

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "p3_gate_result.json"
            write_json(path, result)
            loaded = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(loaded["status"], "ok")
        self.assertEqual(loaded["checks"][0]["name"], "fake_success")
        self.assertIn("api_contract", loaded)
        self.assertIn("secret_scan", loaded)


if __name__ == "__main__":
    unittest.main()
