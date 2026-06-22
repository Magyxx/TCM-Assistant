from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "check_release_packaging.py"
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


class P33ReleasePackagingScriptTests(unittest.TestCase):
    def test_check_release_packaging_json_output_is_ok(self) -> None:
        completed = _run_script("--json", "--output", "")
        payload = json.loads(completed.stdout)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["phase"], "P3.3")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["checks_total"], 12)
        self.assertEqual(payload["checks_passed"], 12)

    def test_default_command_writes_check_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "p3_3_release_packaging_check.json"
            completed = _run_script("--output", str(output_path))
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["manifest"]["phase"], "P3.3")

    def test_release_packaging_output_does_not_leak_openai_key(self) -> None:
        secret = "sk-" + "releasepackagingsecret0001"
        completed = _run_script("--json", "--output", "", env=_clean_env(OPENAI_API_KEY=secret))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn(secret, completed.stdout)
        self.assertNotIn("releasepackagingsecret0001", completed.stdout)


if __name__ == "__main__":
    unittest.main()
