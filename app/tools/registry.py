from __future__ import annotations

from typing import Any, Dict

from app.api.redaction import redact_secrets
from app.tools import eval_case_tool, export_report_tool, rag_search_tool, report_safety_tool, risk_check_tool
from app.tools.audit import build_tool_audit
from app.tools.permissions import permission_denial
from app.tools.schemas import P7ToolDefinition, P7ToolResult, ToolHandler
from app.tools.base import PermissionLevel, ToolCallResult, ToolDefinition
from app.tools.builtin import builtin_tools


class P7ToolRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, P7ToolDefinition] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, definition: P7ToolDefinition, handler: ToolHandler) -> None:
        self._definitions[definition.name] = definition
        self._handlers[definition.name] = handler

    def definitions(self) -> list[P7ToolDefinition]:
        return [self._definitions[name] for name in sorted(self._definitions)]

    def definition(self, name: str) -> P7ToolDefinition | None:
        return self._definitions.get(name)

    def call(self, name: str, payload: Dict[str, Any], *, approved: bool = False) -> P7ToolResult:
        definition = self.definition(name)
        blocked_reason = permission_denial(definition, approved=approved)
        if blocked_reason is not None:
            return P7ToolResult(
                tool_name=name,
                allowed=False,
                blocked_reason=blocked_reason,
                audit_log=build_tool_audit(
                    definition,
                    tool_name=name,
                    payload=payload,
                    approved=approved,
                    allowed=False,
                    blocked_reason=blocked_reason,
                ),
            )
        assert definition is not None
        output = self._handlers[name](payload)
        return P7ToolResult(
            tool_name=name,
            allowed=True,
            output=redact_secrets(output),
            audit_log=build_tool_audit(
                definition,
                tool_name=name,
                payload=payload,
                approved=approved,
                allowed=True,
            ),
        )


def build_p7_registry() -> P7ToolRegistry:
    registry = P7ToolRegistry()
    registry.register(
        P7ToolDefinition(
            name="risk_check_tool",
            description="Rule-first risk signal check.",
            input_schema={"type": "object", "required": ["user_input"]},
            output_schema={"type": "object", "required": ["risk_status", "risk_rule_ids"]},
            permission_level="low",
            side_effect=False,
            requires_human_approval=False,
            audit_log=True,
        ),
        risk_check_tool.invoke,
    )
    registry.register(
        P7ToolDefinition(
            name="rag_search_tool",
            description="Search the approved P6 runtime knowledge index.",
            input_schema={"type": "object", "required": ["query"]},
            output_schema={"type": "object", "required": ["evidence", "rag_boundary_pass"]},
            permission_level="low",
            side_effect=False,
            requires_human_approval=False,
            audit_log=True,
        ),
        rag_search_tool.invoke,
    )
    registry.register(
        P7ToolDefinition(
            name="report_safety_tool",
            description="Validate report safety boundaries.",
            input_schema={"type": "object", "required": ["report"]},
            output_schema={"type": "object", "required": ["passed", "checks"]},
            permission_level="low",
            side_effect=False,
            requires_human_approval=False,
            audit_log=True,
        ),
        report_safety_tool.invoke,
    )
    registry.register(
        P7ToolDefinition(
            name="export_report_tool",
            description="Prepare a redacted report export payload.",
            input_schema={"type": "object", "required": ["report"]},
            output_schema={"type": "object", "required": ["export_ready", "file_written"]},
            permission_level="medium",
            side_effect=True,
            requires_human_approval=True,
            audit_log=True,
        ),
        export_report_tool.invoke,
    )
    registry.register(
        P7ToolDefinition(
            name="eval_case_tool",
            description="Validate a structured evaluation case shape.",
            input_schema={"type": "object", "required": ["case"]},
            output_schema={"type": "object", "required": ["case_valid", "turn_count"]},
            permission_level="low",
            side_effect=False,
            requires_human_approval=False,
            audit_log=True,
        ),
        eval_case_tool.invoke,
    )
    return registry


def _validate_required(schema: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    required = schema.get("required") if isinstance(schema, dict) else None
    if not isinstance(required, list):
        return []
    return [str(field) for field in required if field not in payload]


class ToolRegistry:
    def __init__(self, *, max_permission: PermissionLevel = "medium") -> None:
        self.max_permission = max_permission
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        self._tools[definition.name] = definition

    def list_tools(self) -> list[ToolDefinition]:
        return [self._tools[name] for name in sorted(self._tools)]

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def _permission_allowed(self, definition: ToolDefinition) -> bool:
        order = {"low": 0, "medium": 1, "high": 2}
        return order[definition.permission_level] <= order[self.max_permission]

    def call_tool(self, name: str, payload: dict[str, Any]) -> ToolCallResult:
        definition = self.get_tool(name)
        if definition is None:
            return ToolCallResult(tool_name=name, allowed=False, blocked_reason="tool_not_found")
        if not self._permission_allowed(definition):
            return ToolCallResult(tool_name=name, allowed=False, blocked_reason="permission_denied")
        missing = _validate_required(definition.input_schema, payload)
        if missing:
            return ToolCallResult(
                tool_name=name,
                allowed=False,
                blocked_reason=f"input_schema_missing:{','.join(missing)}",
            )
        if definition.callable is None:
            return ToolCallResult(tool_name=name, allowed=False, blocked_reason="tool_not_callable")
        output = definition.callable(payload)
        missing_output = _validate_required(definition.output_schema, output)
        if missing_output:
            return ToolCallResult(
                tool_name=name,
                allowed=False,
                output=output,
                blocked_reason=f"output_schema_missing:{','.join(missing_output)}",
            )
        return ToolCallResult(tool_name=name, allowed=True, output=redact_secrets(output))


def build_tool_registry(*, max_permission: PermissionLevel = "medium") -> ToolRegistry:
    registry = ToolRegistry(max_permission=max_permission)
    for definition in builtin_tools():
        registry.register(definition)
    return registry
