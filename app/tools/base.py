from __future__ import annotations

from typing import Any, Callable, Literal

from pydantic import BaseModel, Field


PermissionLevel = Literal["low", "medium", "high"]
ToolCallable = Callable[[dict[str, Any]], dict[str, Any]]


class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    permission_level: PermissionLevel = "low"
    side_effect: bool = False
    requires_human_approval: bool = False
    audit_log: bool = True
    callable: ToolCallable | None = Field(default=None, exclude=True)

    model_config = {"arbitrary_types_allowed": True}


class ToolCallResult(BaseModel):
    tool_name: str
    allowed: bool
    output: dict[str, Any] = Field(default_factory=dict)
    blocked_reason: str | None = None

