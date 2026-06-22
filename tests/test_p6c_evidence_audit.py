import unittest

from app.rag.evidence_audit import build_evidence_audit_records, validate_evidence_audit_records
from app.rag.p6_runtime_retriever import P6RuntimeRetriever


class P6CEvidenceAuditTests(unittest.TestCase):
    def test_evidence_audit_records_include_required_metadata(self) -> None:
        pack, trace = P6RuntimeRetriever().retrieve(
            "胸痛 呼吸困难 风险提示",
            top_k=2,
            session_id="audit-unit",
            turn_id="1",
            trace_id="audit-unit-trace",
            write_audit=False,
        )
        records = build_evidence_audit_records(
            pack,
            trace,
            query_id="audit-query",
            used_in_report_section="retrieved",
            core_state_mutated=False,
        )
        validation = validate_evidence_audit_records(records)

        self.assertTrue(validation["evidence_audit_schema_pass"])
        self.assertGreater(validation["record_count"], 0)
        for record in records:
            self.assertEqual(record["trace_id"], "audit-unit-trace")
            self.assertEqual(record["session_id"], "audit-unit")
            self.assertEqual(record["query_id"], "audit-query")
            self.assertTrue(record["source_hash"].startswith("sha256:"))
            self.assertEqual(record["registry_version"], "p6c.registry.v1")
            self.assertEqual(record["review_version"], "p6c.review.v1")
            self.assertTrue(record["approved_for_runtime"])
            self.assertFalse(record["core_state_mutated"])


if __name__ == "__main__":
    unittest.main()
