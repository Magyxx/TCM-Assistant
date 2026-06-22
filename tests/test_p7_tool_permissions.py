from __future__ import annotations

import unittest

from app.tools.registry import build_p7_registry


class P7ToolPermissionTests(unittest.TestCase):
    def test_export_blocks_without_approval_and_unknown_tool_blocks(self) -> None:
        registry = build_p7_registry()
        export_result = registry.call("export_report_tool", {"report": {"summary": "ok"}}, approved=False)
        unknown_result = registry.call("delete_session_tool", {}, approved=True)

        self.assertFalse(export_result.allowed)
        self.assertEqual(export_result.blocked_reason, "human_approval_required")
        self.assertFalse(unknown_result.allowed)
        self.assertEqual(unknown_result.blocked_reason, "unknown_tool")


if __name__ == "__main__":
    unittest.main()
