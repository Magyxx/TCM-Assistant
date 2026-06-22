import unittest

from app.rag.evidence_boundary import (
    attach_evidence_pack,
    build_evidence_pack,
    core_state_snapshot,
)
from app.schemas.report_schemas import FinalReport, RunState


class P43RagBoundaryTests(unittest.TestCase):
    def test_evidence_pack_cannot_write_core_state(self) -> None:
        state = RunState(chief_complaint="腹泻", duration="两天", risk_flags_status="none")
        before = core_state_snapshot(state)

        pack = build_evidence_pack(state, top_k=2, mode="bm25_only")

        self.assertEqual(before, core_state_snapshot(state))
        self.assertTrue(pack.core_state_readonly)
        self.assertIn("chief_complaint", pack.forbidden_state_writes)
        self.assertIn("risk_rule_ids", pack.forbidden_state_writes)
        self.assertFalse(pack.can_diagnose)
        self.assertFalse(pack.can_prescribe)

    def test_attach_evidence_pack_preserves_report_contract_fields(self) -> None:
        report = FinalReport(
            summary="summary",
            impression="仅用于问诊信息整理，不是诊断。",
            advice=["记录变化。"],
            triage_level="observe",
            info_complete=True,
            missing_core_fields=[],
            followup_needed=False,
        )
        pack = build_evidence_pack(RunState(chief_complaint="腹泻", duration="两天"), top_k=1)

        enhanced = attach_evidence_pack(report, pack)

        self.assertEqual(enhanced.summary, report.summary)
        self.assertEqual(enhanced.impression, report.impression)
        self.assertEqual(enhanced.advice, report.advice)
        self.assertEqual(enhanced.triage_level, report.triage_level)
        self.assertIn("p4_rag_evidence_pack", enhanced.metadata)


if __name__ == "__main__":
    unittest.main()

