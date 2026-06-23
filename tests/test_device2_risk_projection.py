import unittest

from app.extractors.risk_projection import project_risk_status
from app.utils.sft_postprocess import postprocess_turn_output


class Device2RiskProjectionTest(unittest.TestCase):
    def test_positive_red_flags_project_present(self) -> None:
        cases = [
            ("高热三天不退，体温39度", "P0_RISK_HIGH_FEVER"),
            ("胸口压着疼，还出汗", "P0_RISK_CHEST_PAIN"),
            ("喘不过气", "P0_RISK_DYSPNEA"),
            ("今天出现便血", "P0_RISK_GI_BLEEDING"),
            ("刚刚呕血了", "P0_RISK_GI_BLEEDING"),
            ("人有点意识模糊", "P0_RISK_CONSCIOUSNESS"),
            ("突发剧烈腹痛", "P0_RISK_SEVERE_ABDOMINAL_PAIN"),
        ]

        for text, rule_id in cases:
            with self.subTest(text=text):
                projection = project_risk_status(user_text=text)
                self.assertEqual(projection.candidate_risk_status, "present")
                self.assertIn(rule_id, projection.candidate_risk_rule_ids)
                self.assertTrue(projection.risk_evidence_spans)

    def test_negated_red_flags_project_none(self) -> None:
        for text in ["没有发热", "不胸痛", "胸口不疼，只是胃胀", "没有呼吸困难", "未见便血"]:
            with self.subTest(text=text):
                projection = project_risk_status(user_text=text)
                self.assertEqual(projection.candidate_risk_status, "none")
                self.assertFalse(projection.candidate_risk_rule_ids)

    def test_previous_present_is_not_downgraded_by_later_negation(self) -> None:
        projection = project_risk_status(
            user_text="现在感觉好一点了，也没有别的不舒服",
            previous_status="present",
            previous_risk_flags=["胸痛"],
            previous_rule_ids=["P0_RISK_CHEST_PAIN"],
        )

        self.assertEqual(projection.candidate_risk_status, "present")
        self.assertIn("胸痛", projection.candidate_risk_flags)
        self.assertIn("P0_RISK_CHEST_PAIN", projection.candidate_risk_rule_ids)

    def test_postprocess_preserves_previous_present_status(self) -> None:
        output = postprocess_turn_output(
            parsed_output={
                "risk_flags": [],
                "risk_flags_status": "none",
                "symptoms": [],
                "symptoms_status": "unknown",
            },
            state_json={
                "risk_flags": ["胸痛"],
                "risk_flags_status": "present",
                "triggered_rule_ids": ["P0_RISK_CHEST_PAIN"],
            },
            user_input="现在感觉好一点了，也没有别的不舒服",
        )

        self.assertEqual(output["risk_flags_status"], "present")
        self.assertIn("胸痛", output["risk_flags"])

    def test_symptom_upgrade_still_requires_risk_recheck(self) -> None:
        output = postprocess_turn_output(
            parsed_output={
                "symptoms": ["发热"],
                "symptoms_status": "present",
                "risk_flags": [],
                "risk_flags_status": "none",
            },
            state_json={
                "symptoms_status": "none",
                "risk_flags": [],
                "risk_flags_status": "none",
            },
            user_input="刚才还出现了发热",
        )

        self.assertEqual(output["risk_flags_status"], "unknown")

    def test_plain_fatigue_after_previous_none_keeps_risk_none(self) -> None:
        output = postprocess_turn_output(
            parsed_output={
                "symptoms": ["乏力"],
                "symptoms_status": "present",
                "risk_flags": [],
                "risk_flags_status": "none",
            },
            state_json={
                "symptoms_status": "none",
                "risk_flags": [],
                "risk_flags_status": "none",
            },
            user_input="后来还有点乏力",
        )

        self.assertEqual(output["risk_flags_status"], "none")


if __name__ == "__main__":
    unittest.main()
