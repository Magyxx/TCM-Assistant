from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT_DIR / "docs"


class P25DeliveryDocsTests(unittest.TestCase):
    def _read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_required_delivery_docs_exist(self) -> None:
        required = [
            "API_CONTRACT.md",
            "SQLITE_SCHEMA.md",
            "SAFETY_BOUNDARY.md",
            "EVAL_CASES.md",
            "LOCAL_RUNBOOK.md",
            "P2_DELIVERY_REPORT.md",
        ]

        for name in required:
            with self.subTest(name=name):
                path = DOCS_DIR / name
                self.assertTrue(path.exists(), name)
                self.assertGreater(len(self._read(path).strip()), 200)

    def test_readme_exposes_p2_entrypoint_and_docs(self) -> None:
        readme = self._read(ROOT_DIR / "README.md")

        self.assertIn("python scripts/run_p2_gate.py", readme)
        self.assertIn("docs/P2_DELIVERY_REPORT.md", readme)
        self.assertIn("docs/LOCAL_RUNBOOK.md", readme)
        self.assertIn("docs/EVAL_CASES.md", readme)
        self.assertIn("P1.1", readme)
        self.assertIn("/health", readme)

    def test_delivery_docs_include_key_commands(self) -> None:
        combined = "\n".join(
            self._read(path)
            for path in [
                ROOT_DIR / "README.md",
                DOCS_DIR / "LOCAL_RUNBOOK.md",
                DOCS_DIR / "EVAL_CASES.md",
                DOCS_DIR / "P2_DELIVERY_REPORT.md",
            ]
        )
        required_commands = [
            "python scripts/run_p2_gate.py",
            "python scripts/run_p1_gate.py",
            "python -m unittest discover -s tests",
            "python scripts/run_case_corpus_eval.py",
            "python scripts/run_long_session_demo.py",
            "python scripts/inspect_sqlite_store.py",
            "python scripts/audit_session.py",
            "python scripts/secret_scan.py",
            "git diff --check",
            "TCM_API_DB_PATH",
        ]

        for command in required_commands:
            with self.subTest(command=command):
                self.assertIn(command, combined)

    def test_health_contract_documented_as_exact_p1_1(self) -> None:
        api_contract = self._read(DOCS_DIR / "API_CONTRACT.md")
        delivery = self._read(DOCS_DIR / "P2_DELIVERY_REPORT.md")

        for text in [api_contract, delivery]:
            with self.subTest():
                self.assertIn("GET /health", text)
                self.assertIn('"stage": "P1.1"', text)
                self.assertIn('"diagnosis_system": false', text)
                self.assertRegex(text.lower(), r"exact")

    def test_delivery_docs_do_not_contain_real_secret_values(self) -> None:
        selected_paths = [
            ROOT_DIR / "README.md",
            DOCS_DIR / "API_CONTRACT.md",
            DOCS_DIR / "SQLITE_SCHEMA.md",
            DOCS_DIR / "SAFETY_BOUNDARY.md",
            DOCS_DIR / "EVAL_CASES.md",
            DOCS_DIR / "LOCAL_RUNBOOK.md",
            DOCS_DIR / "P2_DELIVERY_REPORT.md",
        ]
        combined = "\n".join(self._read(path) for path in selected_paths)

        self.assertIsNone(re.search(r"sk-[A-Za-z0-9_-]{20,}", combined))
        self.assertNotIn("OPENAI_API_KEY=", combined)

    def test_delivery_docs_do_not_claim_medical_capability(self) -> None:
        combined = "\n".join(
            self._read(path).lower()
            for path in [
                ROOT_DIR / "README.md",
                DOCS_DIR / "SAFETY_BOUNDARY.md",
                DOCS_DIR / "P2_DELIVERY_REPORT.md",
            ]
        )
        forbidden_claims = [
            "can diagnose",
            "will diagnose",
            "provides diagnosis",
            "can prescribe",
            "will prescribe",
            "provides prescription",
            "provides treatment plan",
            "treatment decision system",
        ]

        for phrase in forbidden_claims:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, combined)

    def test_delivery_manifest_shape(self) -> None:
        path = ROOT_DIR / "artifacts" / "p2_delivery_manifest.json"
        self.assertTrue(path.exists())
        payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["phase"], "P2.5")
        self.assertIn(payload["status"], {"ok", "pending"})
        self.assertIn("docs", payload)
        self.assertIn("scripts", payload)
        self.assertIn("tests", payload)
        self.assertFalse(payload["boundary_check"]["violated"])


if __name__ == "__main__":
    unittest.main()
