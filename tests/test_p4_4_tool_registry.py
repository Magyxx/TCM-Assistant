import unittest

from app.tools.internal_registry import build_default_registry


class P44ToolRegistryTests(unittest.TestCase):
    def test_default_tools_have_required_metadata(self) -> None:
        registry = build_default_registry()
        definitions = {definition.name: definition for definition in registry.definitions()}

        self.assertEqual(
            set(definitions),
            {
                "risk_check_tool",
                "rag_search_tool",
                "report_safety_tool",
                "export_report_tool",
                "eval_case_tool",
            },
        )
        for definition in definitions.values():
            self.assertTrue(definition.input_schema)
            self.assertTrue(definition.output_schema)
            self.assertIn(definition.permission_level, {"read", "evaluate", "export"})
            self.assertIsInstance(definition.requires_human_approval, bool)
            self.assertTrue(definition.audit_log)

    def test_export_tool_requires_human_approval(self) -> None:
        registry = build_default_registry()

        result = registry.call("export_report_tool", {"report": {"summary": "ok"}}, approved=False)

        self.assertFalse(result.allowed)
        self.assertEqual(result.blocked_reason, "human_approval_required")
        self.assertEqual(result.audit_log["side_effect"], "external_export")

    def test_risk_tool_returns_rule_first_result(self) -> None:
        registry = build_default_registry()

        result = registry.call("risk_check_tool", {"user_input": "我胸痛"}, approved=False)

        self.assertTrue(result.allowed)
        self.assertIn("risk_status", result.output)
        self.assertIn("risk_rule_ids", result.output)
        self.assertTrue(result.audit_log["allowed"])


if __name__ == "__main__":
    unittest.main()

