from __future__ import annotations

import unittest

from app.rules.risk_rules import evaluate_risk_rules
from app.tools.registry import build_p7_registry


class P7SafetyBoundaryTests(unittest.TestCase):
    def test_rule_first_risk_and_tool_overreach_blocking(self) -> None:
        high_risk = evaluate_risk_rules("胸痛并且呼吸困难")
        negated = evaluate_risk_rules("没有胸痛")
        export_result = build_p7_registry().call("export_report_tool", {"report": {}}, approved=False)

        self.assertEqual(high_risk.risk_status, "present")
        self.assertEqual(negated.risk_status, "none")
        self.assertFalse(export_result.allowed)


if __name__ == "__main__":
    unittest.main()
