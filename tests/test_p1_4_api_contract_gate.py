from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class P14ApiContractGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]
        self.script = self.project_root / "scripts" / "validate_p1_api_contract.py"

    def test_contract_gate_passes_with_isolated_db(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "p1_4_contract.sqlite3"
            result = subprocess.run(
                [
                    sys.executable,
                    str(self.script),
                    "--db",
                    str(db_path),
                    "--allow-clear",
                    "--json",
                ],
                cwd=self.project_root,
                check=True,
                capture_output=True,
                text=True,
            )

        payload = json.loads(result.stdout)

        self.assertTrue(payload["passed"])
        self.assertEqual(payload["stage"], "P1.4")
        self.assertEqual(payload["summary"]["health_stage"], "P1.1")
        self.assertFalse(payload["summary"]["diagnosis_system"])
        self.assertEqual(payload["summary"]["turn_count_after_restart"], 1)
        self.assertIsInstance(payload["summary"]["final_report_ready_after_restart"], bool)
        self.assertEqual(payload["summary"]["schema_meta"]["schema_stage"], "P1.3")
        self.assertEqual(
            payload["summary"]["table_counts"],
            {"sessions": 2, "session_states": 2, "turns": 2},
        )
        self.assertTrue(all(check["ok"] for check in payload["checks"]))
        self.assertNotIn("OPENAI_API_KEY", result.stdout)
        self.assertNotIn("sk-contractsecret1234567890", result.stdout)

    def test_db_argument_requires_allow_clear(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(self.script),
                "--db",
                "some.sqlite3",
                "--json",
            ],
            cwd=self.project_root,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("--allow-clear", result.stderr)


if __name__ == "__main__":
    unittest.main()
