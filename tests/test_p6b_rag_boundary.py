import unittest

from app.rag.boundary import (
    RagBoundaryViolation,
    assert_evidence_pack_is_boundary_safe,
    core_state_snapshot,
    rag_boundary_check,
)
from app.rag.evidence_schema import build_empty_p6_evidence_pack
from app.schemas.report_schemas import RunState


def _pack():
    return build_empty_p6_evidence_pack(
        "unit query",
        source_manifest_version="kb.source_manifest.v0",
        index_path="knowledge/indexes/p6_bm25_index.json",
        chunks_path="knowledge/processed/p6_chunks.jsonl",
        source_manifest_path="knowledge/source_manifest.example.json",
    )


class P6BRagBoundaryTests(unittest.TestCase):
    def test_safe_pack_and_unchanged_state_pass_boundary(self) -> None:
        before = RunState(
            chief_complaint="digestive discomfort",
            duration="two days",
            symptoms=["appetite change"],
            risk_flags_status="none",
            triggered_rule_ids=[],
        )
        after = before.model_copy(deep=True)

        result = rag_boundary_check(before, after, _pack())

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["passed"])
        self.assertEqual(core_state_snapshot(before), core_state_snapshot(after))

    def test_chief_complaint_mutation_fails_boundary(self) -> None:
        before = RunState(chief_complaint="digestive discomfort", duration="two days")
        after = before.model_copy(update={"chief_complaint": "chest pain"}, deep=True)

        result = rag_boundary_check(before, after, _pack())

        self.assertEqual(result["status"], "failed")
        self.assertIn("chief_complaint", str(result["violation"]))

    def test_duration_and_risk_rule_mutation_fail_boundary(self) -> None:
        before = RunState(
            chief_complaint="digestive discomfort",
            duration="two days",
            risk_flags_status="present",
            triggered_rule_ids=["red_flag_chest_pain"],
        )
        after = before.model_copy(
            update={"duration": "one week", "triggered_rule_ids": []},
            deep=True,
        )

        result = rag_boundary_check(before, after, _pack())

        self.assertEqual(result["status"], "failed")
        self.assertIn("duration", str(result["violation"]))
        self.assertIn("risk_rule_ids", str(result["violation"]))

    def test_new_core_symptom_from_rag_fails_boundary(self) -> None:
        before = RunState(symptoms=["appetite change"], risk_flags_status="none")
        after = before.model_copy(update={"symptoms": ["appetite change", "chest pain"]}, deep=True)

        result = rag_boundary_check(before, after, _pack())

        self.assertEqual(result["status"], "failed")
        self.assertIn("symptoms", str(result["violation"]))

    def test_negated_risk_cannot_be_changed_to_present(self) -> None:
        before = RunState(risk_flags_status="none", risk_flags=[])
        after = before.model_copy(update={"risk_flags_status": "present", "risk_flags": ["dyspnea"]}, deep=True)

        result = rag_boundary_check(before, after, _pack())

        self.assertEqual(result["status"], "failed")
        self.assertIn("risk_flags_status", str(result["violation"]))

    def test_evidence_pack_with_write_authority_is_rejected(self) -> None:
        pack = _pack()
        pack.core_state_readonly = False

        with self.assertRaisesRegex(RagBoundaryViolation, "core_state_readonly"):
            assert_evidence_pack_is_boundary_safe(pack)

    def test_evidence_pack_with_diagnosis_or_prescription_authority_is_rejected(self) -> None:
        pack = _pack()
        pack.can_diagnose = True
        pack.can_prescribe = True

        with self.assertRaisesRegex(RagBoundaryViolation, "diagnosis/prescription"):
            assert_evidence_pack_is_boundary_safe(pack)


if __name__ == "__main__":
    unittest.main()
