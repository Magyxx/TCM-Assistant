from __future__ import annotations

import unittest

from app.tools.base import ToolResult, ToolSpec
from app.tools.registry import build_tool_registry


class P1F0ToolRegistryTests(unittest.TestCase):
    def test_registry_fields_call_and_errors(self) -> None:
        registry = build_tool_registry(max_permission="medium")
        tools = {tool.name: tool for tool in registry.list_tools()}
        self.assertIn("risk_check_tool", tools)
        self.assertIn("rag_search_tool", tools)
        self.assertTrue(tools["export_report_tool"].side_effect)
        self.assertTrue(tools["export_report_tool"].requires_human_approval)
        self.assertIsInstance(ToolSpec(name="demo", description="demo"), ToolSpec)
        self.assertTrue(ToolResult(tool_name="demo", ok=True).ok)

        risk = registry.call_tool("risk_check_tool", {"user_input": "胸痛伴呼吸困难"})
        self.assertTrue(risk.allowed)
        missing = registry.call_tool("unknown_tool", {})
        self.assertEqual(missing.blocked_reason, "tool_not_found")


if __name__ == "__main__":
    unittest.main()
