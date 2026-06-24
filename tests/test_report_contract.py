from __future__ import annotations

import unittest

from app.report.renderer import build_report_skeleton
from app.report.schemas import FinalReportSkeleton


class P1F0ReportContractTests(unittest.TestCase):
    def test_report_skeleton_schema_and_disclaimer(self) -> None:
        report = build_report_skeleton(session_id="session", state={"risk_status": "unknown"})
        payload = report.model_dump()
        self.assertIsInstance(FinalReportSkeleton.model_validate(payload), FinalReportSkeleton)
        self.assertTrue(payload["safety_disclaimer"])
        self.assertEqual(payload["generated_by"], "deterministic_p1_f0_skeleton")


if __name__ == "__main__":
    unittest.main()
