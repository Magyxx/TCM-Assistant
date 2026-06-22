from __future__ import annotations

from app.tools import eval_case_tool, export_report_tool, rag_search_tool, report_safety_tool, risk_check_tool
from app.tools.base import ToolDefinition


def _reserved_high_tool(payload: dict) -> dict:
    raise PermissionError("high permission tool is reserved and disabled by default")


def builtin_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="risk_check_tool",
            description="Rule-first risk signal check.",
            input_schema={"type": "object", "required": ["user_input"]},
            output_schema={"type": "object", "required": ["risk_status", "risk_rule_ids"]},
            permission_level="low",
            side_effect=False,
            requires_human_approval=False,
            audit_log=True,
            callable=risk_check_tool.invoke,
        ),
        ToolDefinition(
            name="rag_search_tool",
            description="Search approved local knowledge.",
            input_schema={"type": "object", "required": ["query"]},
            output_schema={"type": "object", "required": ["evidence"]},
            permission_level="low",
            side_effect=False,
            requires_human_approval=False,
            audit_log=True,
            callable=rag_search_tool.invoke,
        ),
        ToolDefinition(
            name="report_safety_tool",
            description="Validate report safety boundaries.",
            input_schema={"type": "object", "required": ["report"]},
            output_schema={"type": "object", "required": ["passed"]},
            permission_level="low",
            side_effect=False,
            requires_human_approval=False,
            audit_log=True,
            callable=report_safety_tool.invoke,
        ),
        ToolDefinition(
            name="eval_case_tool",
            description="Validate a structured eval case shape.",
            input_schema={"type": "object", "required": ["case"]},
            output_schema={"type": "object", "required": ["case_valid"]},
            permission_level="low",
            side_effect=False,
            requires_human_approval=False,
            audit_log=True,
            callable=eval_case_tool.invoke,
        ),
        ToolDefinition(
            name="export_report_tool",
            description="Prepare a redacted export payload.",
            input_schema={"type": "object", "required": ["report"]},
            output_schema={"type": "object", "required": ["export_ready"]},
            permission_level="medium",
            side_effect=True,
            requires_human_approval=False,
            audit_log=True,
            callable=export_report_tool.invoke,
        ),
        ToolDefinition(
            name="delete_session_tool",
            description="Reserved high-risk session deletion tool; not implemented.",
            input_schema={"type": "object", "required": ["session_id"]},
            output_schema={"type": "object"},
            permission_level="high",
            side_effect=True,
            requires_human_approval=True,
            audit_log=True,
            callable=_reserved_high_tool,
        ),
        ToolDefinition(
            name="external_api_tool",
            description="Reserved external medical API tool; not connected.",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            permission_level="high",
            side_effect=True,
            requires_human_approval=True,
            audit_log=True,
            callable=_reserved_high_tool,
        ),
    ]

