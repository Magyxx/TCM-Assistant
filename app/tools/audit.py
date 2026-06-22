from __future__ import annotations

from typing import Any, Dict

from app.api.redaction import redact_secrets
from app.storage.models import utc_now
from app.tools.schemas import P7ToolDefinition


def build_tool_audit(
    definition: P7ToolDefinition | None,
    *,
    tool_name: str,
    payload: Dict[str, Any],
    approved: bool,
    allowed: bool,
    blocked_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "ts": utc_now(),
        "tool_name": tool_name,
        "permission_level": definition.permission_level if definition else None,
        "side_effect": definition.side_effect if definition else None,
        "requires_human_approval": definition.requires_human_approval if definition else None,
        "approved": bool(approved),
        "allowed": bool(allowed),
        "blocked_reason": blocked_reason,
        "payload": redact_secrets(payload),
    }
