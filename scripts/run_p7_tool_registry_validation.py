from __future__ import annotations

from typing import Any

try:
    from p7_common import ROOT_DIR, check, status_from_checks, write_json
except ImportError:  # pragma: no cover - package import path
    from scripts.p7_common import ROOT_DIR, check, status_from_checks, write_json

from app.tools.registry import build_p7_registry  # noqa: E402


ARTIFACT = ROOT_DIR / "artifacts" / "p7_tool_registry_validation.json"


def run_p7_tool_registry_validation(*, write_artifact: bool = True) -> dict[str, Any]:
    registry = build_p7_registry()
    definitions = registry.definitions()
    by_name = {definition.name: definition for definition in definitions}
    expected = {
        "risk_check_tool",
        "rag_search_tool",
        "report_safety_tool",
        "export_report_tool",
        "eval_case_tool",
    }
    export_blocked = registry.call("export_report_tool", {"report": {"summary": "ok"}}, approved=False)
    risk_result = registry.call("risk_check_tool", {"user_input": "我胸痛"}, approved=False)
    unknown = registry.call("delete_session_tool", {}, approved=True)
    checks = [
        check("tool_registry_schema_pass", set(by_name) == expected and all(definition.version and definition.input_schema and definition.output_schema for definition in definitions)),
        check("tool_permission_levels_pass", all(definition.permission_level in {"low", "medium", "high"} for definition in definitions)),
        check("tool_export_requires_approval", export_blocked.allowed is False and export_blocked.blocked_reason == "human_approval_required"),
        check("tool_risk_rule_first_pass", risk_result.allowed and risk_result.output.get("risk_status") == "present"),
        check("tool_permission_violation_count", unknown.allowed is False and unknown.blocked_reason == "unknown_tool"),
        check("tool_audit_log_pass", bool(risk_result.audit_log.get("tool_name")) and risk_result.audit_log.get("allowed") is True),
    ]
    payload = {
        "phase": "P7",
        "status": status_from_checks(checks),
        "checks": checks,
        "metrics": {
            "tool_registry_schema_pass": checks[0]["ok"],
            "tool_permission_violation_count": 0 if checks[4]["ok"] else 1,
            "tool_audit_log_pass": checks[5]["ok"],
            "tool_count": len(definitions),
        },
        "tools": [definition.model_dump() for definition in definitions],
    }
    if write_artifact:
        write_json(ARTIFACT, payload)
    return payload


def main() -> int:
    payload = run_p7_tool_registry_validation()
    print(f"P7 tool registry validation: status={payload['status']} artifact={ARTIFACT.relative_to(ROOT_DIR)}")
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
