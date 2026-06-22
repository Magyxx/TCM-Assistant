from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.secret_scan import scan_paths


REALISTIC_SECRET = "sk-" + "realisticsecret123456789012345"
SYNTHETIC_SECRET = "sk-" + "testsecret123456789012345"
SQLITE_SECRET = "sk-" + "sqlitesecret123456789012345"


class P16SecretScanTests(unittest.TestCase):
    def test_detects_sk_pattern_in_text_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "app").mkdir()
            (root / "app" / "leak.txt").write_text(f"value={REALISTIC_SECRET}", encoding="utf-8")

            result = scan_paths([root])

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["finding_count"], 1)
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn(REALISTIC_SECRET, serialized)
        self.assertIn("[redacted-secret]", serialized)

    def test_allowlists_synthetic_test_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "tests").mkdir()
            (root / "tests" / "test_secret.py").write_text(SYNTHETIC_SECRET, encoding="utf-8")

            result = scan_paths([root])

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["finding_count"], 0)
        self.assertEqual(result["allowed_count"], 1)

    def test_synthetic_secret_outside_tests_is_not_allowlisted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "docs").mkdir()
            (root / "docs" / "leak.md").write_text(SYNTHETIC_SECRET, encoding="utf-8")

            result = scan_paths([root])

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["finding_count"], 1)

    def test_scans_sqlite_file_for_unredacted_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "leak.sqlite3").write_text(f"payload {SQLITE_SECRET}", encoding="utf-8")

            result = scan_paths([root], include_runtime=True)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["finding_count"], 1)

    def test_redacted_secret_literal_is_not_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "safe.txt").write_text("[redacted-secret]", encoding="utf-8")

            result = scan_paths([root])

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["finding_count"], 0)

    def test_local_env_file_is_excluded_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text(f"OPENAI_API_KEY={REALISTIC_SECRET}", encoding="utf-8")
            (root / ".env.example").write_text("OPENAI_API_KEY=your_api_key_here", encoding="utf-8")

            result = scan_paths([root])

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["finding_count"], 0)

    def test_json_output_shape_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = scan_paths([Path(temp_dir)])

        self.assertEqual(
            set(result.keys()),
            {
                "phase",
                "status",
                "scanned_files",
                "finding_count",
                "allowed_count",
                "findings",
                "allowed_findings",
                "allowlist",
                "include_runtime",
            },
        )
        json.dumps(result, ensure_ascii=False)

    def test_preview_redaction_handles_json_escaped_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "tests").mkdir()
            escaped = '"\\u80c3\\u80c0\\uff0cOPENAI_API_KEY=' + SYNTHETIC_SECRET + '"'
            (root / "tests" / "test_escaped_secret.json").write_text(escaped, encoding="utf-8")

            result = scan_paths([root])

        serialized = json.dumps(result, ensure_ascii=False)
        self.assertEqual(result["status"], "ok")
        self.assertNotIn(SYNTHETIC_SECRET, serialized)
        self.assertNotIn("\\[redacted-secret]", serialized)
        json.loads(serialized)


if __name__ == "__main__":
    unittest.main()
