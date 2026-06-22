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
SCRIPT = ROOT_DIR / "scripts" / "check_runtime_config.py"
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


class P31RuntimeConfigScriptTests(unittest.TestCase):
    def test_json_output_is_valid(self) -> None:
        completed = _run_script("--json")
        payload = json.loads(completed.stdout)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["phase"], "P3.1")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["runtime_config"]["runtime_mode"], "local")
        self.assertIsInstance(payload["checks"], list)
        self.assertIsInstance(payload["warnings"], list)
        self.assertIsInstance(payload["errors"], list)

    def test_all_modes_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            for mode in ["local", "test", "demo", "eval"]:
                with self.subTest(mode=mode):
                    db_path = str(Path(temp_dir) / f"{mode}.sqlite3")
                    completed = _run_script("--json", "--mode", mode, "--db", db_path)
                    payload = json.loads(completed.stdout)

                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    self.assertEqual(payload["runtime_config"]["runtime_mode"], mode)
                    self.assertEqual(payload["runtime_config"]["db_path_source"], "cli:--db")

    def test_db_cli_override_takes_priority_over_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_db = str(Path(temp_dir) / "env.sqlite3")
            cli_db = str(Path(temp_dir) / "cli.sqlite3")
            completed = _run_script(
                "--json",
                "--db",
                cli_db,
                env=_clean_env(TCM_API_DB_PATH=env_db),
            )
            payload = json.loads(completed.stdout)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["runtime_config"]["db_path"], cli_db)
        self.assertEqual(payload["runtime_config"]["db_path_source"], "cli:--db")

    def test_invalid_mode_exits_nonzero_with_json_errors(self) -> None:
        completed = _run_script("--json", "--mode", "invalid")
        payload = json.loads(completed.stdout)

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(payload["status"], "failed")
        self.assertTrue(any("Invalid runtime_mode" in error for error in payload["errors"]))

    def test_invalid_boolean_env_exits_nonzero(self) -> None:
        completed = _run_script("--json", env=_clean_env(TCM_ALLOW_REAL_LLM="sometimes"))
        payload = json.loads(completed.stdout)

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(payload["status"], "failed")
        self.assertTrue(any("Invalid boolean env TCM_ALLOW_REAL_LLM" in error for error in payload["errors"]))

    def test_output_artifact_can_be_written(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "p3_1_runtime_config.json"
            completed = _run_script("--json", "--output", str(output_path))
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["phase"], "P3.1")
        self.assertIn("runtime_config", payload)

    def test_openai_api_key_value_is_not_leaked(self) -> None:
        secret = "sk-" + "scriptsecret0001"
        completed = _run_script("--json", env=_clean_env(OPENAI_API_KEY=secret))
        payload = json.loads(completed.stdout)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(payload["runtime_config"]["openai_api_key_present"])
        self.assertNotIn(secret, completed.stdout)
        self.assertNotIn("OPENAI_API_KEY", completed.stdout)

    def test_errors_and_warnings_shape_is_stable(self) -> None:
        completed = _run_script("--json", "--mode", "eval")
        payload = json.loads(completed.stdout)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIsInstance(payload["warnings"], list)
        self.assertIsInstance(payload["errors"], list)
        self.assertTrue(any("temporary database" in warning for warning in payload["warnings"]))

    def test_p2_gate_includes_runtime_config_check_without_losing_existing_checks(self) -> None:
        names = [spec["name"] for spec in default_check_specs(skip_long_session=True)]

        self.assertIn("runtime_config_check", names)
        self.assertIn("p1_gate", names)
        self.assertIn("unittest_discover", names)
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


if __name__ == "__main__":
    unittest.main()
