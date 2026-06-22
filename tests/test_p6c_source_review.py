import json
import tempfile
import unittest
from pathlib import Path

from app.knowledge.source_registry import DEFAULT_SOURCE_REGISTRY_PATH, load_source_registry, write_json
from app.knowledge.source_review import review_source_registry, source_review_hard_pass


class P6CSourceReviewTests(unittest.TestCase):
    def test_source_review_records_smoke_only_as_fail_closed_warning(self) -> None:
        payload = review_source_registry(registry_path=DEFAULT_SOURCE_REGISTRY_PATH)
        reviews = {item["source_id"]: item for item in payload["reviews"]}

        self.assertTrue(source_review_hard_pass(payload))
        self.assertEqual(payload["approved_for_runtime_count"], 1)
        self.assertEqual(reviews["synthetic_p6_policy_001"]["status"], "approved")
        self.assertEqual(reviews["synthetic_smoke_001"]["status"], "skipped")
        self.assertTrue(reviews["synthetic_smoke_001"]["warnings"])

    def test_runtime_source_with_unknown_rights_fails_review(self) -> None:
        registry = load_source_registry(DEFAULT_SOURCE_REGISTRY_PATH)
        mutated = json.loads(json.dumps(registry, ensure_ascii=False))
        target = next(source for source in mutated["sources"] if source["source_id"] == "synthetic_p6_policy_001")
        target["rights_status"] = "unknown"

        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "source_registry.json"
            write_json(registry_path, mutated)
            payload = review_source_registry(registry_path=registry_path)

        self.assertFalse(source_review_hard_pass(payload))
        self.assertTrue(payload["review_failures"])


if __name__ == "__main__":
    unittest.main()
