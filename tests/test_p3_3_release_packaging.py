from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from scripts.check_release_packaging import (
    ABSOLUTE_PATH_PATTERN,
    build_release_packaging_payload,
)
from scripts.run_p2_gate import default_check_specs


ROOT_DIR = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT_DIR / "artifacts" / "p3_3_release_packaging.json"
RELEASE_DOC_PATH = ROOT_DIR / "docs" / "RELEASE_PACKAGING.md"
ENV_EXAMPLE_PATH = ROOT_DIR / ".env.example"


class P33ReleasePackagingTests(unittest.TestCase):
    def test_release_manifest_json_is_parseable(self) -> None:
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

        self.assertEqual(payload["phase"], "P3.3")
        self.assertEqual(payload["status"], "ok")
        self.assertFalse(payload["contract_changed"])
        self.assertFalse(payload["sqlite_schema_changed"])
        self.assertFalse(payload["boundary_violated"])

    def test_release_manifest_contains_no_secret_or_local_absolute_path(self) -> None:
        text = MANIFEST_PATH.read_text(encoding="utf-8")

        self.assertNotIn("sk-", text)
        self.assertNotIn("OPENAI_API_KEY", text)
        self.assertIsNone(ABSOLUTE_PATH_PATTERN.search(text))

    def test_env_example_exists_and_contains_only_placeholder_key(self) -> None:
        text = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")

        self.assertIn("TCM_RUNTIME_MODE=local", text)
        self.assertIn("TCM_ALLOW_REAL_LLM=false", text)
        self.assertIn("TCM_REDACT_LOGS=true", text)
        self.assertRegex(text, r"(?m)^OPENAI_API_KEY=$")
        self.assertIsNone(re.search(r"sk-[A-Za-z0-9_-]{20,}", text))

    def test_release_packaging_doc_contains_reproducibility_commands(self) -> None:
        text = RELEASE_DOC_PATH.read_text(encoding="utf-8")

        self.assertIn('python -m unittest discover -s tests -p "test*.py"', text)
        self.assertIn("python scripts/check_runtime_config.py", text)
        self.assertIn("python scripts/check_observability.py", text)
        self.assertIn("python scripts/check_release_packaging.py", text)

    def test_release_packaging_doc_states_safety_boundary(self) -> None:
        text = RELEASE_DOC_PATH.read_text(encoding="utf-8")

        for phrase in ["不诊断", "不开方", "不替代医生", "高风险提示线下就医"]:
            self.assertIn(phrase, text)
        self.assertIn("production medical product", text)
        self.assertIn("prescription system", text)

    def test_release_packaging_payload_is_ok(self) -> None:
        payload = build_release_packaging_payload()

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["phase"], "P3.3")
        self.assertEqual(payload["checks_total"], 12)
        self.assertEqual(payload["checks_passed"], 12)

    def test_p2_gate_includes_release_packaging_check(self) -> None:
        names = [spec["name"] for spec in default_check_specs(skip_long_session=True)]

        self.assertIn("runtime_config_check", names)
        self.assertIn("observability_check", names)
        self.assertIn("release_packaging_check", names)
        self.assertIn("api_contract_check", names)


if __name__ == "__main__":
    unittest.main()
