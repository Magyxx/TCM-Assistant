from __future__ import annotations

from app.tools.schemas import P7ToolDefinition


def permission_denial(definition: P7ToolDefinition | None, *, approved: bool) -> str | None:
    if definition is None:
        return "unknown_tool"
    if not definition.enabled:
        return "tool_disabled"
    if definition.permission_level == "high":
        return "high_permission_tool_not_enabled_in_p7"
    if definition.requires_human_approval and not approved:
        return "human_approval_required"
    return None
