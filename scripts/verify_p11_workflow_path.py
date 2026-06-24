from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

STAGE = "P11-M3_WORKFLOW_MAIN_PATH"
DEFAULT_OUTPUT = ROOT_DIR / "artifacts" / "p11" / "workflow_path_contract.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_graph(user_input: str, *, extractor_backend: str = "fake", use_langgraph: bool = False) -> dict[str, Any]:
    from app.graph.runner import run_p9m1_graph

    with tempfile.TemporaryDirectory() as temp_dir:
        return run_p9m1_graph(
            user_input,
            extractor_backend=extractor_backend,
            use_langgraph=use_langgraph,
            graph_events_path=Path(temp_dir) / "graph_events.jsonl",
        )


def _trace_nodes(result: dict[str, Any]) -> list[str]:
    return [str(item.get("node")) for item in result.get("trace") or [] if item.get("node")]


def _node_order_ok(nodes: list[str], ordered_nodes: list[str]) -> bool:
    positions = []
    for node in ordered_nodes:
        if node not in nodes:
            return False
        positions.append(nodes.index(node))
    return positions == sorted(positions)


def _fallback_runtime_probe() -> dict[str, Any]:
    from app.graph.edges import P9_NODE_NAMES

    result = _run_graph(
        "stomach discomfort for two days, no other symptoms, no chest pain, sleep normal, appetite normal, stool normal, urination normal",
        use_langgraph=False,
    )
    nodes = _trace_nodes(result)
    expected_order = [
        "normalize_input",
        "extract_turn",
        "validate_turn",
        "merge_state",
        "risk_rule_check",
        "decide_next",
    ]
    checks = {
        "fallback_runtime_passed": result.get("graph_runtime") == "sequential_fallback",
        "node_sequence_declared": P9_NODE_NAMES[: len(expected_order)] == expected_order,
        "trace_order_passed": _node_order_ok(nodes, expected_order),
        "schema_guard_in_path": result.get("schema_valid") is True and "validate_turn" in nodes,
        "state_update_in_path": "merge_state" in nodes and (result.get("run_state") or {}).get("turn_count") == 1,
        "risk_rules_in_path": "risk_rule_check" in nodes,
        "audit_trace_recorded": bool(result.get("trace")) and bool(result.get("graph_events")),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "graph_runtime": result.get("graph_runtime"),
        "trace_nodes": nodes,
        "risk_status": result.get("risk_status"),
        "next_question": result.get("next_question"),
        "final_report_ready": result.get("final_report") is not None,
    }


def _optional_langgraph_probe() -> dict[str, Any]:
    from app.graph.runtime import is_langgraph_available

    if not is_langgraph_available():
        return {
            "status": "skipped",
            "skip_reason": "langgraph is not installed",
            "passed": True,
        }
    result = _run_graph(
        "stomach discomfort for two days, no other symptoms, no chest pain, sleep normal, appetite normal, stool normal, urination normal",
        use_langgraph=True,
    )
    return {
        "status": "passed" if result.get("graph_runtime") == "langgraph" else "failed",
        "passed": result.get("graph_runtime") == "langgraph",
        "graph_runtime": result.get("graph_runtime"),
        "trace_nodes": _trace_nodes(result),
    }


def _risk_rules_probe() -> dict[str, Any]:
    from app.rules.risk_rules import RISK_RULES

    risk_text = f"{RISK_RULES[0].trigger_keywords[0]} {RISK_RULES[1].trigger_keywords[0]}"
    result = _run_graph(risk_text, use_langgraph=False)
    rule_ids = result.get("risk_rule_ids") or []
    passed = result.get("risk_status") == "present" and bool(rule_ids)
    return {
        "passed": passed,
        "risk_status": result.get("risk_status"),
        "risk_rule_ids": rule_ids,
        "trace_nodes": _trace_nodes(result),
    }


def _local_lora_bypass_probe() -> dict[str, Any]:
    from app.extractors.openai_compatible_client import OpenAICompatibleChatClient
    from app.rules.risk_rules import RISK_RULES

    def mock_completion(self, messages):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "chief_complaint": "stomach discomfort",
                                "duration": "half a day",
                                "symptoms": [],
                                "symptoms_status": "none",
                                "risk_flags": [],
                                "risk_flags_status": "none",
                                "summary": "candidate attempted to clear risk",
                            }
                        )
                    }
                }
            ]
        }

    risk_text = f"{RISK_RULES[0].trigger_keywords[0]} {RISK_RULES[1].trigger_keywords[0]}"
    with patch.object(OpenAICompatibleChatClient, "create_chat_completion", mock_completion):
        result = _run_graph(
            risk_text,
            extractor_backend="local_lora",
            use_langgraph=False,
        )
    extraction = result.get("extracted_turn_output") or {}
    metadata = extraction.get("metadata") or {}
    rule_ids = result.get("risk_rule_ids") or []
    passed = (
        metadata.get("backend") == "local_lora"
        and result.get("risk_status") == "present"
        and bool(rule_ids)
        and (result.get("run_state") or {}).get("risk_flags_status") == "present"
    )
    return {
        "passed": passed,
        "candidate_backend": metadata.get("backend"),
        "candidate_risk_flags_status": extraction.get("risk_flags_status"),
        "final_risk_status": result.get("risk_status"),
        "risk_rule_ids": rule_ids,
        "trace_nodes": _trace_nodes(result),
    }


def verify() -> dict[str, Any]:
    import subprocess

    fallback = _fallback_runtime_probe()
    optional = _optional_langgraph_probe()
    risk = _risk_rules_probe()
    local_lora = _local_lora_bypass_probe()
    checks = {
        "fallback_runtime_passed": fallback["checks"]["fallback_runtime_passed"],
        "schema_guard_in_path": fallback["checks"]["schema_guard_in_path"],
        "state_update_in_path": fallback["checks"]["state_update_in_path"],
        "risk_rules_fallback_in_path": bool(risk["passed"]),
        "audit_trace_recorded": fallback["checks"]["audit_trace_recorded"],
        "optional_graph_runtime_passed_or_skipped": bool(optional["passed"]),
        "local_lora_bypass_blocked": bool(local_lora["passed"]),
    }
    status = "ok" if all(checks.values()) else "failed"
    git = lambda args: subprocess.run(
        ["git", *args],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    ).stdout.strip()
    return {
        "stage": STAGE,
        "status": status,
        "branch": git(["branch", "--show-current"]),
        "commit": git(["rev-parse", "HEAD"]),
        "origin_main": git(["rev-parse", "origin/main"]),
        "checks": checks,
        "fallback_runtime": fallback,
        "optional_graph_runtime": optional,
        "risk_rules_fallback": risk,
        "local_lora_bypass": local_lora,
        "workflow_contract": {
            "schema_validate_node": "validate_turn",
            "state_update_node": "merge_state",
            "risk_rules_node": "risk_rule_check",
            "next_action_node": "decide_next",
            "report_readiness_node": "generate_report",
            "audit_events": "trace and graph_events",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify P11-M3 workflow main path contract.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Artifact output path.")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    result = verify()
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT_DIR / output
    _write_json(output, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(result["status"])
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
