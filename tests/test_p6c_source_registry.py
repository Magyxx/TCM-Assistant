import unittest

from app.knowledge.source_registry import (
    DEFAULT_SOURCE_REGISTRY_PATH,
    load_source_registry,
    validate_source_registry,
)


class P6CSourceRegistryTests(unittest.TestCase):
    def test_registry_schema_and_runtime_permissions_pass(self) -> None:
        registry = load_source_registry(DEFAULT_SOURCE_REGISTRY_PATH)
        result = validate_source_registry(registry, registry_path=DEFAULT_SOURCE_REGISTRY_PATH)

        self.assertEqual(result["phase"], "P6C")
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["source_registry_schema_pass"])
        self.assertEqual(result["source_count"], 2)
        self.assertEqual(result["approved_for_runtime_count"], 1)
        self.assertEqual(result["approved_for_eval_count"], 1)
        self.assertEqual(result["approved_for_training_count"], 0)
        self.assertEqual(result["unknown_rights_count"], 1)
        self.assertFalse(result["source_validation_errors"])

    def test_runtime_permission_does_not_imply_training_permission(self) -> None:
        registry = load_source_registry(DEFAULT_SOURCE_REGISTRY_PATH)
        runtime_source = next(
            source for source in registry["sources"] if source["source_id"] == "synthetic_p6_policy_001"
        )

        self.assertTrue(runtime_source["approved_for_runtime"])
        self.assertTrue(runtime_source["approved_for_eval"])
        self.assertFalse(runtime_source["approved_for_training"])
        self.assertFalse(runtime_source["approved_for_public_demo"])


if __name__ == "__main__":
    unittest.main()
