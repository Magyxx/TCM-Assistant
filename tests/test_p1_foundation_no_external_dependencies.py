from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from app.config.settings import AppSettings


class P1F0NoExternalDependenciesTests(unittest.TestCase):
    def test_settings_defaults_are_safe(self) -> None:
        settings = AppSettings.from_env({})
        self.assertEqual(settings.EXTRACTOR_BACKEND, "fake")
        self.assertFalse(settings.ENABLE_REAL_LLM)
        self.assertFalse(settings.ENABLE_LOCAL_LORA)
        self.assertFalse(settings.ENABLE_RAG)
        self.assertEqual(settings.RAG_BACKEND, "bm25_stub")
        self.assertEqual(settings.DATABASE_URL, "sqlite:///./artifacts/local_demo.db")

    def test_verify_script_writes_artifact(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "p1_foundation_validation.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/verify_p1_foundation.py",
                    "--json",
                    "--output",
                    str(output),
                ],
                cwd=root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ok")
            self.assertFalse(payload["external_dependencies_required"])
            self.assertEqual(payload["skipped_external"]["real_llm"], "skipped_by_design")


if __name__ == "__main__":
    unittest.main()
