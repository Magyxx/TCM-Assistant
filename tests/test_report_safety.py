from __future__ import annotations

from app.safety.report_safety import safety_post_check_report
from app.schemas.report_schemas import FinalReport


def test_report_safety_removes_diagnosis_and_prescription_like_phrases() -> None:
    report = FinalReport(
        summary="诊断为某病",
        impression="诊断为某病，建议服用某某药方。",
        advice=["建议服用某某药方。"],
        triage_level="observe",
        info_complete=True,
        missing_core_fields=[],
        followup_needed=False,
    )

    checked = safety_post_check_report(report).report
    text = checked.summary + checked.impression + "".join(checked.advice)
    assert "诊断为" not in text
    assert "建议服用某某药方" not in text
    assert checked.safety_disclaimer
