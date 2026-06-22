# P7 Tool Registry

## Tools
- `risk_check_tool`: low permission, no side effect, no approval.
- `rag_search_tool`: low permission, no side effect, no approval.
- `report_safety_tool`: low permission, no side effect, no approval.
- `export_report_tool`: medium permission, side effect, approval required.
- `eval_case_tool`: low permission, no side effect, no approval.

## Metadata
Every tool declares `name`, `description`, `input_schema`, `output_schema`, `permission_level`, `side_effect`, `requires_human_approval`, `audit_log`, `version`, and `enabled`.

## Boundaries
P7 does not expose `delete_session_tool`, external API tools, MCP Server, free tool calling, or high-risk automatic tool execution. Unknown and disabled tools are blocked and audited.
