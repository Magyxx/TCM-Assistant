from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.run_p2_gate import (
    exit_code_for_result,
    run_p2_gate,
    summarize_p2_gate,
    write_json,
)


def _check(name: str, code: str) -> dict[str, object]:
    return {
        "name": name,
        "command": [sys.executable, "-c", code],
        "timeout_seconds": 30,
    }


class P25P2GateRunnerTests(unittest.TestCase):
    def test_single_fake_check_success_sets_status_ok(self) -> None:
        result = run_p2_gate(check_specs=[_check("fake_success", "print('ok')")])

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["total_checks"], 1)
        self.assertEqual(result["passed"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["checks"][0]["status"], "ok")
        self.assertEqual(exit_code_for_result(result), 0)

    def test_single_fake_check_failure_sets_status_failed(self) -> None:
        result = run_p2_gate(
            check_specs=[
                _check(
                    "fake_failure",
                    "import sys; print('before fail'); sys.stderr.write('bad\\n'); sys.exit(7)",
                )
            ]
        )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["checks"][0]["return_code"], 7)
        self.assertEqual(exit_code_for_result(result), 1)

    def test_fail_fast_stops_after_first_failure(self) -> None:
        result = run_p2_gate(
            check_specs=[
                _check("first_failure", "import sys; sys.exit(2)"),
                _check("should_not_run", "print('unexpected')"),
            ],
            fail_fast=True,
        )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["total_checks"], 1)
        self.assertEqual(result["checks"][0]["name"], "first_failure")

    def test_stdout_and_stderr_tails_are_redacted(self) -> None:
        secret = "sk-" + "gatefake1234567890"
        result = run_p2_gate(
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

    def test_artifact_can_be_written(self) -> None:
        result = run_p2_gate(check_specs=[_check("fake_success", "print('ok')")])

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "p2_gate_result.json"
            write_json(path, result)
            loaded = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(loaded["status"], "ok")
        self.assertEqual(loaded["checks"][0]["name"], "fake_success")
        self.assertIn("secret_scan", loaded)
        self.assertNotIn("[redacted-secret-key]", loaded)

    def test_summary_shape_contains_delivery_sections(self) -> None:
        result = summarize_p2_gate(
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
            ],
            skip_long_session=True,
        )

        self.assertEqual(result["phase"], "P2.5")
        self.assertIn("p1_gate", result)
        self.assertIn("case_corpus_eval", result)
        self.assertIn("long_session", result)
        self.assertIn("release_packaging_check", result)
        self.assertIn("secret_scan", result)
        self.assertIn("api_contract_check", result)
        self.assertEqual(result["current_gate_phase"], "P3.4")
        self.assertTrue(result["long_session"]["skipped"])
        self.assertFalse(result["boundary_check"]["violated"])


if __name__ == "__main__":
    unittest.main()
