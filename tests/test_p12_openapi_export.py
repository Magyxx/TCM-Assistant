from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.export_openapi import export_openapi


class P12OpenAPIExportTests(unittest.TestCase):
    def test_openapi_export_can_target_p12_artifact_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p12-openapi-") as temp:
            path = export_openapi(Path(temp) / "openapi.json")

            self.assertTrue(path.exists())
            schema = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("/health", schema["paths"])
        self.assertIn("/sessions", schema["paths"])
        self.assertIn("/sessions/{session_id}/turn", schema["paths"])
        self.assertNotIn("OPENAI_API_KEY", json.dumps(schema, ensure_ascii=False))
        self.assertNotIn("sk-", json.dumps(schema, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
