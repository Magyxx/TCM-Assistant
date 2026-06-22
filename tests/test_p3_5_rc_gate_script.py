from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "run_p3_gate.py"
TCM_ENV_KEYS = [
    "TCM_RUNTIME_MODE",
    "TCM_API_DB_PATH",
    "TCM_RUNTIME_DIR",
    "TCM_ARTIFACTS_DIR",
    "TCM_ALLOW_REAL_LLM",
    "TCM_LOG_LEVEL",
    "TCM_REDACT_LOGS",
    "TCM_CONFIG_STRICT",
    "OPENAI_API_KEY",
]


def _clean_env(**extra: str) -> dict[str, str]:
    env = os.environ.copy()
    for key in TCM_ENV_KEYS:
        env.pop(key, None)
    env["PYTHONPATH"] = str(ROOT_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    env.update(extra)
    return env


def _run_script(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env or _clean_env(),
        timeout=60,
    )


class P35RcGateScriptTests(unittest.TestCase):
    def test_summary_only_json_output_is_ok(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "p3_gate_result.json"
            rc_output_path = Path(temp_dir) / "p3_5_rc_gate.json"
            completed = _run_script(
                "--summary-only",
                "--json",
                "--output",
                str(output_path),
                "--rc-output",
                str(rc_output_path),
            )
            payload = json.loads(completed.stdout)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["stage"], "P3.5")
        self.assertEqual(payload["current_gate_phase"], "P3.5")
        self.assertEqual(payload["recommend_next"], "P4.0")
        self.assertEqual(payload["api_version"], "v1")
        self.assertEqual(payload["api_contract_status"], "frozen")
        self.assertFalse(payload["breaking_change_detected"])
        self.assertEqual(payload["boundary_violations"], [])
        self.assertEqual(payload["checks_total"], 11)

    def test_default_command_writes_primary_and_rc_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "p3_gate_result.json"
            rc_output_path = Path(temp_dir) / "p3_5_rc_gate.json"
            completed = _run_script(
                "--summary-only",
                "--output",
                str(output_path),
                "--rc-output",
                str(rc_output_path),
            )
            primary = json.loads(output_path.read_text(encoding="utf-8"))
            rc_payload = json.loads(rc_output_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(primary["status"], "ok")
        self.assertEqual(rc_payload["status"], "ok")
        self.assertEqual(primary["current_gate_phase"], "P3.5")
        self.assertEqual(primary, rc_payload)

    def test_summary_only_output_does_not_leak_openai_key(self) -> None:
        secret = "sk-" + "p35scriptsecret0001"
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "p3_gate_result.json"
            rc_output_path = Path(temp_dir) / "p3_5_rc_gate.json"
            completed = _run_script(
                "--summary-only",
                "--json",
                "--output",
                str(output_path),
                "--rc-output",
                str(rc_output_path),
                env=_clean_env(OPENAI_API_KEY=secret),
            )
            combined = (
                completed.stdout
                + output_path.read_text(encoding="utf-8")
                + rc_output_path.read_text(encoding="utf-8")
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn(secret, combined)
        self.assertNotIn("p35scriptsecret0001", combined)
        self.assertNotIn("OPENAI_API_KEY", combined)


if __name__ == "__main__":
    unittest.main()
