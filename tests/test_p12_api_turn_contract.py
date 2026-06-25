from __future__ import annotations

import unittest

from scripts.verify_p12_api_contract import verify


class P12ApiTurnContractTests(unittest.TestCase):
    def test_turn_contract_goes_through_risk_rules_and_safety_boundary(self) -> None:
        payload = verify()

        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["checks"]["turn_returns_contract"])
        self.assertTrue(payload["checks"]["risk_rules_fallback_high_risk"])
        self.assertTrue(payload["checks"]["no_forbidden_medical_output"])
        self.assertEqual(payload["high_risk_contract"]["risk_flags_status"], "present")


if __name__ == "__main__":
    unittest.main()
