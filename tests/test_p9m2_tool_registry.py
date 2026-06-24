from __future__ import annotations

from app.tools.registry import build_tool_registry


def test_low_risk_tools_list_and_call() -> None:
    registry = build_tool_registry(max_permission="medium")
    names = {tool.name for tool in registry.list_tools()}

    assert "risk_check_tool" in names
    result = registry.call_tool("risk_check_tool", {"user_input": "胸痛伴呼吸困难"})
    assert result.allowed
    assert result.output["risk_status"] == "present"


def test_high_risk_reserved_tool_blocked_by_default() -> None:
    registry = build_tool_registry(max_permission="medium")
    result = registry.call_tool("delete_session_tool", {"session_id": "x"})

    assert not result.allowed
    assert result.blocked_reason == "permission_denied"
