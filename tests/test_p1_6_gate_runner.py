from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.run_p1_gate import run_checks, run_command_check, summarize_gate


class P16GateRunnerTests(unittest.TestCase):
    def test_single_check_success_status_is_ok(self) -> None:
        check, _ = run_command_check(
            "success",
            [sys.executable, "-c", "print('ok')"],
        )

        self.assertEqual(check["status"], "ok")
        self.assertEqual(check["return_code"], 0)
        self.assertIn("ok", check["stdout_tail"])

    def test_single_check_failure_sets_failed_status(self) -> None:
        check, _ = run_command_check(
            "failure",
            [sys.executable, "-c", "import sys; print('bad'); sys.exit(3)"],
        )

        self.assertEqual(check["status"], "failed")
        self.assertEqual(check["return_code"], 3)

    def test_fail_fast_stops_after_first_failure(self) -> None:
        checks = [
            ("first", [sys.executable, "-c", "print('first')"]),
            ("bad", [sys.executable, "-c", "import sys; sys.exit(2)"]),
            ("never", [sys.executable, "-c", "print('never')"]),
        ]

        results = run_checks(checks, fail_fast=True)

        self.assertEqual([item["name"] for item in results], ["first", "bad"])
        self.assertEqual(results[-1]["status"], "failed")

    def test_stdout_and_stderr_tails_are_redacted(self) -> None:
        secret = "sk-" + "gateoutputsecret1234567890"
        check, _ = run_command_check(
            "redaction",
            [
                sys.executable,
                "-c",
                (
                    "import sys; "
                    f"print('OPENAI_API_KEY={secret}'); "
                    f"print('TOKEN={secret}', file=sys.stderr)"
                ),
            ],
        )
        serialized = json.dumps(check, ensure_ascii=False)

        self.assertEqual(check["status"], "ok")
        self.assertNotIn(secret, serialized)
        self.assertNotIn("OPENAI_API_KEY", serialized)
        self.assertNotIn("TOKEN=", serialized)

    def test_gate_summary_json_result(self) -> None:
        checks = [
            {
                "name": "ok",
                "command": "fake",
                "status": "ok",
                "return_code": 0,
                "duration_seconds": 0.01,
                "stdout_tail": "",
                "stderr_tail": "",
            }
        ]

        result = summarize_gate(checks)

        self.assertEqual(result["phase"], "P1.6")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["passed"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["recommend_next"], "P1 Final Gate")
        json.dumps(result, ensure_ascii=False)

    def test_gate_summary_failure_semantics(self) -> None:
        checks = [
            {
                "name": "bad",
                "command": "fake",
                "status": "failed",
                "return_code": 1,
                "duration_seconds": 0.01,
                "stdout_tail": "",
                "stderr_tail": "",
            }
        ]

        result = summarize_gate(checks)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["passed"], 0)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["recommend_next"], "hold")

    def test_artifact_can_be_written_by_caller(self) -> None:
        result = summarize_gate([])
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "gate.json"
            path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            loaded = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(loaded["phase"], "P1.6")


if __name__ == "__main__":
    unittest.main()
