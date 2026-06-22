import json
import tempfile
import unittest
from pathlib import Path

from app.knowledge.pipeline import (
    CHUNK_SCHEMA_VERSION,
    INGESTIBLE_RIGHTS_STATUSES,
    FORBIDDEN_STATE_WRITES,
    run_p6_pipeline,
)


class P6KnowledgePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_p6_pipeline(write_outputs=False)

    def test_p6_pipeline_completes_without_runtime_contract_changes(self) -> None:
        result = self.result

        self.assertEqual(result["phase"], "P6")
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["runtime_changes"])
        self.assertFalse(result["api_schema_changes"])
        self.assertFalse(result["sqlite_changes"])
        self.assertFalse(result["risk_rule_changes"])
        self.assertFalse(result["large_real_book_ingestion"])
        self.assertFalse(result["diagnosis_system"])

    def test_source_review_only_indexes_approved_p6_sources(self) -> None:
        review = self.result["source_review"]
        reviews_by_id = {item["source_id"]: item for item in review["reviews"]}

        self.assertEqual(review["approved_source_count"], 1)
        self.assertEqual(review["skipped_source_count"], 1)
        self.assertEqual(review["blocked_source_count"], 0)
        self.assertEqual(reviews_by_id["synthetic_smoke_001"]["status"], "skipped")
        self.assertEqual(reviews_by_id["synthetic_p6_policy_001"]["status"], "approved")
        self.assertEqual(
            {chunk["source_id"] for chunk in self.result["_chunks"]},
            {"synthetic_p6_policy_001"},
        )

    def test_chunks_conform_to_schema_and_preserve_rights_metadata(self) -> None:
        chunks = self.result["_chunks"]
        required = {
            "chunk_id",
            "source_id",
            "source_type",
            "title",
            "section",
            "content",
            "entities",
            "normalized_terms",
            "risk_level",
            "trust_level",
            "rights_status",
            "version",
            "hash",
        }

        self.assertGreaterEqual(len(chunks), 2)
        for chunk in chunks:
            self.assertEqual(chunk["schema_version"], CHUNK_SCHEMA_VERSION)
            self.assertLessEqual(required - set(chunk), set())
            self.assertIn(chunk["rights_status"], INGESTIBLE_RIGHTS_STATUSES)
            self.assertTrue(chunk["hash"].startswith("sha256:"))
            self.assertIn("allowed_use", chunk["provenance"])
            self.assertIn("forbidden_use", chunk["provenance"])

    def test_index_and_eval_cover_retrieval_and_safety_boundary(self) -> None:
        index = self.result["_index"]
        evaluation = self.result["evaluation"]
        boundary = self.result["rag_boundary"]

        self.assertEqual(index["chunk_count"], self.result["chunking"]["chunk_count"])
        self.assertIn("inverted_index", index)
        self.assertEqual(evaluation["status"], "ok")
        self.assertEqual(evaluation["retrieval_quality"]["passed_count"], 2)
        self.assertEqual(evaluation["safety_boundary"]["status"], "ok")
        self.assertTrue(boundary["core_state_readonly"])
        self.assertTrue(boundary["risk_rule_first"])
        self.assertFalse(boundary["can_diagnose"])
        self.assertFalse(boundary["can_prescribe"])
        self.assertLessEqual(set(FORBIDDEN_STATE_WRITES), set(boundary["forbidden_state_writes"]))

    def test_approved_source_without_review_flags_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_dir = root / "raw"
            raw_dir.mkdir()
            (raw_dir / "note.txt").write_text(
                "Section: Safety\nChest pain requires offline care.",
                encoding="utf-8",
            )
            manifest = {
                "schema_version": "kb.source_manifest.v0",
                "sources": [
                    {
                        "source_id": "missing_review",
                        "title": "Missing Review",
                        "author": "fixture",
                        "edition": "v0",
                        "publisher": "internal",
                        "source_type": "internal_policy_note",
                        "rights_status": "internal_owned",
                        "license": "internal-test-fixture-only",
                        "allowed_use": ["P6 clean chunk index eval pipeline"],
                        "forbidden_use": ["diagnosis", "prescription generation"],
                        "ingestion_status": "approved_for_p6",
                        "trust_level": "fixture_low",
                        "review_required": True,
                        "content_path": "raw/note.txt",
                    }
                ],
            }
            manifest_path = root / "source_manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            result = run_p6_pipeline(manifest_path=manifest_path, write_outputs=False)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["source_review"]["blocked_source_count"], 1)
        self.assertEqual(result["chunking"]["chunk_count"], 0)
        self.assertIn("review flags", result["source_review"]["reviews"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
