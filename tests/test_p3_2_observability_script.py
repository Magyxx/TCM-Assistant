from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.run_p2_gate import default_check_specs, run_p2_gate


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "check_observability.py"
TCM_ENV_KEYS = [
    "TCM_RUNTIME_MODE",
    "TCM_API_DB_PATH",
    "TCM_LOG_LEVEL",
    "TCM_REDACT_LOGS",
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


class P32ObservabilityScriptTests(unittest.TestCase):
    def test_check_observability_json_output_is_ok(self) -> None:
        completed = _run_script("--json")
        payload = json.loads(completed.stdout)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["phase"], "P3.2")
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["structured_logging"])
        self.assertTrue(payload["redaction_enabled"])
        self.assertTrue(payload["request_id_supported"])

    def test_default_command_writes_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "p3_2_observability.json"
            completed = _run_script("--output", str(output_path))
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["status"], "ok")
        self.assertIn("sample_event", payload)

    def test_observability_output_does_not_leak_openai_key(self) -> None:
        secret = "sk-" + "scriptobservabilitysecret0001"
        completed = _run_script("--json", env=_clean_env(OPENAI_API_KEY=secret))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn(secret, completed.stdout)
        self.assertNotIn("scriptobservabilitysecret0001", completed.stdout)
        self.assertNotIn("OPENAI_API_KEY", completed.stdout)

    def test_p2_gate_includes_observability_check(self) -> None:
        names = [spec["name"] for spec in default_check_specs(skip_long_session=True)]

        self.assertIn("runtime_config_check", names)
        self.assertIn("observability_check", names)
        self.assertIn("p1_gate", names)

    def test_p2_gate_summary_has_observability_section(self) -> None:
        result = run_p2_gate(
            check_specs=[
                {
                    "name": "fake_success",
                    "command": [sys.executable, "-c", "print('ok')"],
                    "timeout_seconds": 30,
                }
            ]
        )

        self.assertEqual(result["status"], "ok")
        self.assertIn("observability_check", result)
        self.assertEqual(result["current_gate_phase"], "P3.4")


if __name__ == "__main__":
    unittest.main()
