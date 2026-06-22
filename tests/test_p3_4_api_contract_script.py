from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = ROOT_DIR / "scripts" / "check_api_contract.py"
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


class P34ApiContractScriptTests(unittest.TestCase):
    def test_check_api_contract_json_output_is_ok(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "p3_4_api_contract_check.json"
            snapshot_path = Path(temp_dir) / "p3_4_api_contract_snapshot.json"
            completed = _run_script(
                "--json",
                "--output",
                str(output_path),
                "--snapshot-output",
                str(snapshot_path),
            )
            payload = json.loads(completed.stdout)
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["phase"], "P3.4")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["api_version"], "v1")
        self.assertEqual(payload["contract_status"], "frozen")
        self.assertEqual(payload["checks_total"], 16)
        self.assertEqual(payload["checks_passed"], 16)
        self.assertEqual(snapshot["api_version"], "v1")
        self.assertEqual(snapshot["contract_status"], "frozen")

    def test_default_command_writes_check_and_snapshot_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "p3_4_api_contract_check.json"
            snapshot_path = Path(temp_dir) / "p3_4_api_contract_snapshot.json"
            completed = _run_script("--output", str(output_path), "--snapshot-output", str(snapshot_path))
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["public_endpoint_count"], len(snapshot["public_endpoints"]))
        self.assertTrue(payload["version_headers_supported"])

    def test_check_api_contract_output_does_not_leak_openai_key(self) -> None:
        secret = "sk-" + "p34contractsecret0001"
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "p3_4_api_contract_check.json"
            snapshot_path = Path(temp_dir) / "p3_4_api_contract_snapshot.json"
            completed = _run_script(
                "--json",
                "--output",
                str(output_path),
                "--snapshot-output",
                str(snapshot_path),
                env=_clean_env(OPENAI_API_KEY=secret),
            )
            payload_text = output_path.read_text(encoding="utf-8")
            snapshot_text = snapshot_path.read_text(encoding="utf-8")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        combined = completed.stdout + payload_text + snapshot_text
        self.assertNotIn(secret, combined)
        self.assertNotIn("p34contractsecret0001", combined)
        self.assertNotIn("OPENAI_API_KEY", combined)


if __name__ == "__main__":
    unittest.main()