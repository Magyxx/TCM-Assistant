from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Literal

from pydantic import BaseModel, Field

from app.api.redaction import redact_secrets
from app.api.report_validator import validate_report
from app.rag.hybrid_retriever import HybridRetriever
from app.rules.risk_rules import evaluate_risk_rules


PermissionLevel = Literal["read", "evaluate", "export"]


class ToolDefinition(BaseModel):
    name: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    permission_level: PermissionLevel
    side_effect: str
    requires_human_approval: bool
    audit_log: bool = True


class ToolExecutionResult(BaseModel):
    tool_name: str
    allowed: bool
    output: Dict[str, Any] = Field(default_factory=dict)
    audit_log: Dict[str, Any] = Field(default_factory=dict)
    blocked_reason: str | None = None


ToolHandler = Callable[[Dict[str, Any]], Dict[str, Any]]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class InternalToolRegistry:
    def __init__(self) -> None:
        self._definitions: Dict[str, ToolDefinition] = {}
        self._handlers: Dict[str, ToolHandler] = {}

    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        self._definitions[definition.name] = definition
        self._handlers[definition.name] = handler

    def definitions(self) -> List[ToolDefinition]:
        return [self._definitions[name] for name in sorted(self._definitions)]

    def definition(self, name: str) -> ToolDefinition:
        return self._definitions[name]

    def call(self, name: str, payload: Dict[str, Any], *, approved: bool = False) -> ToolExecutionResult:
        if name not in self._definitions:
            return ToolExecutionResult(
                tool_name=name,
                allowed=False,
                blocked_reason="unknown_tool",
                audit_log={
                    "ts": _now_iso(),
                    "tool_name": name,
                    "allowed": False,
                    "payload": redact_secrets(payload),
                },
            )

        definition = self._definitions[name]
        audit = {
            "ts": _now_iso(),
            "tool_name": name,
            "permission_level": definition.permission_level,
            "side_effect": definition.side_effect,
            "requires_human_approval": definition.requires_human_approval,
            "approved": bool(approved),
            "payload": redact_secrets(payload),
        }
        if definition.requires_human_approval and not approved:
            return ToolExecutionResult(
                tool_name=name,
                allowed=False,
                blocked_reason="human_approval_required",
                audit_log={**audit, "allowed": False},
            )

        output = self._handlers[name](payload)
        return ToolExecutionResult(
            tool_name=name,
            allowed=True,
            output=redact_secrets(output),
            audit_log={**audit, "allowed": True},
        )


def _risk_check(payload: Dict[str, Any]) -> Dict[str, Any]:
    evaluation = evaluate_risk_rules(
        str(payload.get("user_input") or ""),
        previous_status=str(payload.get("previous_status") or "unknown"),
    )
    return {
        "risk_status": evaluation.risk_status,
        "risk_flags": evaluation.risk_flags,
        "risk_rule_ids": evaluation.triggered_rule_ids,
        "risk_reasons": evaluation.risk_reasons,
        "negated_rule_ids": evaluation.negated_rule_ids,
    }


def _rag_search(payload: Dict[str, Any]) -> Dict[str, Any]:
    query = str(payload.get("query") or "")
    top_k = int(payload.get("top_k") or 3)
    evidence = HybridRetriever(mode="bm25_only").retrieve(query, top_k=top_k)
    return {
        "evidence": [item.model_dump() for item in evidence],
        "core_state_readonly": True,
        "can_overwrite_risk_status": False,
    }


def _report_safety(payload: Dict[str, Any]) -> Dict[str, Any]:
    return validate_report(payload.get("report"), payload.get("state"))


def _export_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "export_ready": True,
        "file_written": False,
        "report": payload.get("report"),
        "note": "P4.4 default export tool prepares a redacted payload; file writes require a separate approved implementation.",
    }


def _eval_case(payload: Dict[str, Any]) -> Dict[str, Any]:
    case = payload.get("case") or {}
    turns = case.get("turns") if isinstance(case, dict) else None
    expected = case.get("expected") if isinstance(case, dict) else None
    return {
        "case_valid": isinstance(turns, list) and bool(turns),
        "turn_count": len(turns) if isinstance(turns, list) else 0,
        "has_expected": isinstance(expected, dict),
        "diagnosis_system": False,
    }


def build_default_registry() -> InternalToolRegistry:
    registry = InternalToolRegistry()
    registry.register(
        ToolDefinition(
            name="risk_check_tool",
            input_schema={"type": "object", "required": ["user_input"]},
            output_schema={"type": "object", "required": ["risk_status", "risk_rule_ids"]},
            permission_level="evaluate",
            side_effect="none",
            requires_human_approval=False,
        ),
        _risk_check,
    )
    registry.register(
        ToolDefinition(
            name="rag_search_tool",
            input_schema={"type": "object", "required": ["query"]},
            output_schema={"type": "object", "required": ["evidence", "core_state_readonly"]},
            permission_level="read",
            side_effect="none",
            requires_human_approval=False,
        ),
        _rag_search,
    )
    registry.register(
        ToolDefinition(
            name="report_safety_tool",
            input_schema={"type": "object", "required": ["report"]},
            output_schema={"type": "object", "required": ["passed", "checks"]},
            permission_level="evaluate",
            side_effect="none",
            requires_human_approval=False,
        ),
        _report_safety,
    )
    registry.register(
        ToolDefinition(
            name="export_report_tool",
            input_schema={"type": "object", "required": ["report"]},
            output_schema={"type": "object", "required": ["export_ready", "file_written"]},
            permission_level="export",
            side_effect="external_export",
            requires_human_approval=True,
        ),
        _export_report,
    )
    registry.register(
        ToolDefinition(
            name="eval_case_tool",
            input_schema={"type": "object", "required": ["case"]},
            output_schema={"type": "object", "required": ["case_valid", "turn_count"]},
            permission_level="evaluate",
            side_effect="none",
            requires_human_approval=False,
        ),
        _eval_case,
    )
    return registry

