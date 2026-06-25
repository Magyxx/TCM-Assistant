from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.schemas.report_schemas import FinalReport


def _report_payload() -> dict:
    return {
        "summary": "Structured intake summary.",
        "impression": "Inquiry support only.",
        "advice": ["Track symptom changes and seek offline care for red flags."],
        "triage_level": "followup",
        "info_complete": True,
        "missing_core_fields": [],
        "followup_needed": False,
        "evidence_citations": [
            {
                "citation_id": "EV001",
                "chunk_id": "chunk-1",
                "source_id": "safety_boundaries",
                "title": "Safety boundaries",
            }
        ],
        "evidence_ids": ["EV001"],
        "citation_coverage": {"status": "passed", "coverage": 1.0},
        "metadata": {"contract": "p11_m5"},
    }


class P11M5FinalReportSchemaTests(unittest.TestCase):
    def test_final_report_schema_exposes_safety_and_evidence_fields(self) -> None:
        report = FinalReport.model_validate(_report_payload())
        payload = report.model_dump()

        for field in [
            "summary",
            "impression",
            "advice",
            "triage_level",
            "info_complete",
            "missing_core_fields",
            "followup_needed",
            "safety_disclaimer",
            "evidence_citations",
            "evidence_ids",
            "citation_coverage",
            "metadata",
        ]:
            self.assertIn(field, payload)

        self.assertEqual(report.triage_level, "followup")
        self.assertTrue(report.safety_disclaimer)
        self.assertEqual(report.evidence_ids, ["EV001"])

    def test_invalid_triage_level_is_rejected(self) -> None:
        payload = _report_payload()
        payload["triage_level"] = "diagnose"

        with self.assertRaises(ValidationError):
            FinalReport.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
