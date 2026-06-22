import unittest

from app.safety.report_safety import SAFETY_BOUNDARY_TEXT, safety_post_check_report
from app.schemas.report_schemas import FinalReport


CANONICAL_SAFETY_BOUNDARY_TEXT = (
    "本系统仅用于问诊信息整理和风险提示，不构成诊断或治疗建议，不能替代医生判断。"
    "如出现持续高热、胸痛、呼吸困难、便血、意识异常、剧烈腹痛等高风险信号，应及时线下就医。"
)


def make_report(impression: str, advice: list[str] | None = None, triage_level: str = "observe") -> FinalReport:
    return FinalReport(
        summary="主诉：胃胀",
        impression=impression,
        advice=advice or ["建议记录症状变化。"],
        triage_level=triage_level,
        info_complete=True,
        missing_core_fields=[],
        followup_needed=False,
    )


class P0ReportSafetyTest(unittest.TestCase):
    def test_diagnosis_phrase_is_removed(self):
        result = safety_post_check_report(make_report("你被诊断为某病。"))

        self.assertTrue(result.rewritten)
        self.assertNotIn("诊断为", result.report.impression)
        self.assertIn(SAFETY_BOUNDARY_TEXT, result.report.impression)

    def test_prescription_phrase_is_removed(self):
        result = safety_post_check_report(make_report("当前情况稳定。", ["建议使用处方药。"]))

        self.assertTrue(result.rewritten)
        self.assertNotIn("处方", "".join(result.report.advice))

    def test_safe_advice_is_allowed(self):
        result = safety_post_check_report(
            make_report(
                "建议就医评估，可记录症状变化。",
                ["如出现高风险信号及时就医。"],
            )
        )

        self.assertFalse(result.rewritten)
        self.assertIn("建议就医评估", result.report.impression)
        self.assertIn("如出现高风险信号及时就医。", result.report.advice)

    def test_standard_boundary_is_not_rewritten(self):
        result = safety_post_check_report(make_report(SAFETY_BOUNDARY_TEXT, [SAFETY_BOUNDARY_TEXT]))

        self.assertFalse(result.rewritten)
        self.assertEqual(result.report.impression, SAFETY_BOUNDARY_TEXT)
        self.assertEqual(result.report.advice.count(SAFETY_BOUNDARY_TEXT), 1)

    def test_urgent_visit_is_preserved_for_high_risk(self):
        result = safety_post_check_report(
            make_report(
                "当前出现高风险信号，建议尽快线下就医。",
                ["建议尽快线下就医评估。"],
                triage_level="urgent_visit",
            )
        )

        self.assertEqual(result.report.triage_level, "urgent_visit")
        self.assertTrue(any("就医" in item for item in result.report.advice))

    def test_structured_fields_are_not_deleted(self):
        report = make_report("当前仅作问诊整理。")
        result = safety_post_check_report(report)

        self.assertEqual(result.report.triage_level, report.triage_level)
        self.assertEqual(result.report.info_complete, report.info_complete)
        self.assertEqual(result.report.missing_core_fields, report.missing_core_fields)
        self.assertEqual(result.report.followup_needed, report.followup_needed)
        self.assertEqual(SAFETY_BOUNDARY_TEXT, CANONICAL_SAFETY_BOUNDARY_TEXT)
        self.assertIn("不构成诊断或治疗建议", SAFETY_BOUNDARY_TEXT)
        self.assertIn("不能替代医生判断", SAFETY_BOUNDARY_TEXT)
        self.assertIn("持续高热、胸痛、呼吸困难、便血、意识异常、剧烈腹痛", SAFETY_BOUNDARY_TEXT)
        self.assertIn("及时线下就医", SAFETY_BOUNDARY_TEXT)


if __name__ == "__main__":
    unittest.main()
