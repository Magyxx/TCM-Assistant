import unittest

from app.rules.risk_rules import (
    RISK_RULES,
    apply_risk_evaluation_to_state,
    evaluate_risk_rules,
    should_stop_routine_followup,
)
from app.graphs.consultation_graph import run_consultation_graph
from app.schemas.report_schemas import RunState


class P0RiskRulesTest(unittest.TestCase):
    def test_normal_fever_is_not_high_fever(self):
        evaluation = evaluate_risk_rules("我发烧了")

        self.assertIsNone(evaluation.risk_status)
        self.assertNotIn("P0_RISK_HIGH_FEVER", evaluation.triggered_rule_ids)

    def test_continuous_high_fever_triggers_risk(self):
        evaluation = evaluate_risk_rules("我持续高烧三天")

        self.assertEqual(evaluation.risk_status, "present")
        self.assertIn("P0_RISK_HIGH_FEVER", evaluation.triggered_rule_ids)
        self.assertIn("持续高热", evaluation.risk_flags)

    def test_negated_chest_pain_does_not_trigger_risk(self):
        evaluation = evaluate_risk_rules("没有胸痛")

        self.assertEqual(evaluation.risk_status, "none")
        self.assertNotIn("P0_RISK_CHEST_PAIN", evaluation.triggered_rule_ids)
        self.assertIn("P0_RISK_CHEST_PAIN", evaluation.negated_rule_ids)

    def test_short_negation_before_blood_in_stool(self):
        evaluation = evaluate_risk_rules("不便血")

        self.assertEqual(evaluation.risk_status, "none")
        self.assertNotIn("P0_RISK_GI_BLEEDING", evaluation.triggered_rule_ids)
        self.assertIn("P0_RISK_GI_BLEEDING", evaluation.negated_rule_ids)

    def test_later_dyspnea_upgrades_previous_none_to_present(self):
        state = RunState(
            chief_complaint="咳嗽",
            duration="一天",
            symptoms_status="none",
            risk_flags_status="none",
        )

        evaluation = evaluate_risk_rules("后来胸闷喘不上气")
        new_state = apply_risk_evaluation_to_state(state, evaluation)

        self.assertEqual(new_state.risk_flags_status, "present")
        self.assertIn("P0_RISK_DYSPNEA", new_state.triggered_rule_ids)
        self.assertIn("呼吸困难", new_state.risk_flags)

    def test_present_risk_does_not_downgrade_when_next_turn_has_no_risk(self):
        state = RunState(
            risk_flags_status="present",
            risk_flags=["呼吸困难"],
            triggered_rule_ids=["P0_RISK_DYSPNEA"],
        )

        evaluation = evaluate_risk_rules("今天稍微好一点")
        new_state = apply_risk_evaluation_to_state(state, evaluation)

        self.assertEqual(new_state.risk_flags_status, "present")
        self.assertIn("呼吸困难", new_state.risk_flags)

    def test_high_risk_stops_routine_followup(self):
        state = RunState(risk_flags_status="present", risk_flags=["胸痛"])

        self.assertTrue(should_stop_routine_followup(state))

    def test_each_rule_has_rule_id(self):
        for rule in RISK_RULES:
            self.assertTrue(rule.rule_id)
            self.assertTrue(rule.reason_template)

    def test_short_fever_is_not_redflag(self):
        evaluation = evaluate_risk_rules("我短暂发热了一下")

        self.assertNotEqual(evaluation.risk_status, "present")

    def test_negated_fever_is_not_redflag(self):
        evaluation = evaluate_risk_rules("没有发热")

        self.assertNotEqual(evaluation.risk_status, "present")

    def test_positive_redflag_examples_have_no_false_negative(self):
        examples = [
            ("我持续高热三天", "P0_RISK_HIGH_FEVER"),
            ("我胸痛", "P0_RISK_CHEST_PAIN"),
            ("我呼吸困难", "P0_RISK_DYSPNEA"),
            ("我便血", "P0_RISK_GI_BLEEDING"),
            ("我呕血", "P0_RISK_GI_BLEEDING"),
            ("我剧烈腹痛", "P0_RISK_SEVERE_ABDOMINAL_PAIN"),
            ("我意识模糊", "P0_RISK_CONSCIOUSNESS"),
        ]

        for text, rule_id in examples:
            with self.subTest(text=text):
                evaluation = evaluate_risk_rules(text)
                self.assertEqual(evaluation.risk_status, "present")
                self.assertIn(rule_id, evaluation.triggered_rule_ids)
                self.assertTrue(evaluation.risk_reasons)

    def test_negated_chest_pain_and_gi_bleeding_are_not_present(self):
        for text in ["没有胸痛", "不便血", "没有呕血"]:
            with self.subTest(text=text):
                evaluation = evaluate_risk_rules(text)
                self.assertNotEqual(evaluation.risk_status, "present")
                self.assertFalse(evaluation.triggered_rule_ids)

    def test_report_contains_rule_ids_and_reasons(self):
        graph_state = run_consultation_graph(
            RunState(),
            "我胸痛",
            use_langgraph=False,
            extractor_mode="rule_fallback",
        )
        report = graph_state["run_state"].final_report

        self.assertIsNotNone(report)
        self.assertIn("P0_RISK_CHEST_PAIN", report.metadata["triggered_rule_ids"])
        self.assertTrue(report.metadata["risk_reasons"])


if __name__ == "__main__":
    unittest.main()
