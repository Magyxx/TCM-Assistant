from __future__ import annotations

from typing import Any, Callable, Dict, Literal, Optional

from pydantic import BaseModel, Field


PermissionLevel = Literal["low", "medium", "high"]
ToolHandler = Callable[[Dict[str, Any]], Dict[str, Any]]


class P7ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    permission_level: PermissionLevel
    side_effect: bool
    requires_human_approval: bool
    audit_log: bool
    version: str = "1.0.0"
    enabled: bool = True


class P7ToolResult(BaseModel):
    tool_name: str
    allowed: bool
    output: Dict[str, Any] = Field(default_factory=dict)
    audit_log: Dict[str, Any] = Field(default_factory=dict)
    blocked_reason: Optional[str] = None
