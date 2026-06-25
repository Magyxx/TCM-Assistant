from __future__ import annotations

import unittest

from scripts.verify_p12_report_eval_api import verify


class P12ApiSafetyBoundaryTests(unittest.TestCase):
    def test_high_risk_report_keeps_urgent_triage_and_no_medical_claims(self) -> None:
        payload = verify()

        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["checks"]["high_risk_triage_preserved"])
        self.assertEqual(payload["report_contract"]["triage_level"], "urgent_visit")
        self.assertTrue(payload["safety_boundaries"]["no_diagnosis"])
        self.assertTrue(payload["safety_boundaries"]["no_prescription"])


if __name__ == "__main__":
    unittest.main()
