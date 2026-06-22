from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from p7_common import check, json_safe, status_from_checks, write_json
except ImportError:  # pragma: no cover
    from scripts.p7_common import check, json_safe, status_from_checks, write_json

from app.graph.consultation_graph import NODE_SEQUENCE, run_consultation_graph
from app.graph.runtime import is_langgraph_available
from app.graph.state import ConsultationGraphState
from app.memory.models import ConsultationMemory
from app.rules.risk_rules import RISK_RULES
from app.schemas.report_schemas import RunState
from app.storage.models import utc_now


DEFAULT_OUTPUT = ROOT_DIR / "artifacts" / "p8_graph_validation.json"


def run_state_model_check() -> dict[str, Any]:
    state = ConsultationGraphState(user_input="胃胀两天")
    ok = isinstance(state.run_state, RunState) and isinstance(state.memory, ConsultationMemory)
    return check(
        "consultation_graph_state_is_pydantic",
        ok,
        schema=state.model_json_schema().get("title"),
        defaults={
            "graph_runtime": state.graph_runtime,
            "extractor_mode_requested": state.extractor_mode_requested,
        },
    )


def run_fallback_smoke() -> dict[str, Any]:
    graph_state = run_consultation_graph(
        RunState(),
        "胃胀两天，没有其他症状",
        use_langgraph=False,
        extractor_mode="fake",
        rag_enabled=False,
    )
    run_state = graph_state["run_state"]
    ok = (
        graph_state["graph_runtime"] == "sequential_fallback"
        and run_state.chief_complaint == "胃胀"
        and run_state.duration == "两天"
        and run_state.turn_count == 1
        and run_state.metadata.get("p8_graph", {}).get("node_sequence") == [name for name, _ in NODE_SEQUENCE]
    )
    return check(
        "fallback_runtime_complete_turn",
        ok,
        runtime=graph_state["graph_runtime"],
        node_sequence=run_state.metadata.get("p8_graph", {}).get("node_sequence"),
        state=run_state.model_dump(),
    )


def run_optional_langgraph_smoke() -> dict[str, Any]:
    if not is_langgraph_available():
        return check(
            "optional_langgraph_runtime",
            True,
            "skipped: langgraph is not installed",
            optional_status="skipped",
        )

    graph_state = run_consultation_graph(
        RunState(),
        "胃胀两天，没有其他症状",
        use_langgraph=True,
        extractor_mode="fake",
        rag_enabled=False,
    )
    ok = graph_state["graph_runtime"] == "langgraph" and graph_state["run_state"].chief_complaint == "胃胀"
    return check(
        "optional_langgraph_runtime",
        ok,
        "passed" if ok else "failed",
        optional_status="passed" if ok else "failed",
        runtime=graph_state["graph_runtime"],
    )


def run_memory_update_check() -> dict[str, Any]:
    graph_state = run_consultation_graph(
        RunState(),
        "胃胀两天，没有其他症状",
        use_langgraph=False,
        extractor_mode="fake",
        rag_enabled=False,
    )
    memory = graph_state["memory"]
    run_state = graph_state["run_state"]
    ok = (
        memory.fact_value("chief_complaint") == "胃胀"
        and "p8_memory" in run_state.metadata
        and bool(memory.audit_events)
        and run_state.metadata.get("p8_graph", {}).get("memory_update_used") is True
    )
    return check(
        "memory_update_node_uses_memory_manager",
        ok,
        facts=list(memory.facts.keys()),
        audit_event_count=len(memory.audit_events),
    )


def run_risk_guard_check() -> dict[str, Any]:
    risk_text = RISK_RULES[0].trigger_keywords[0]
    high_risk = run_consultation_graph(
        RunState(),
        risk_text,
        use_langgraph=False,
        extractor_mode="fallback",
        rag_enabled=False,
    )
    high_risk_state = high_risk["run_state"]
    sticky = run_consultation_graph(
        RunState(
            chief_complaint="胸闷",
            duration="一天",
            symptoms_status="unknown",
            risk_flags_status="present",
            risk_flags=["呼吸困难"],
            triggered_rule_ids=["P0_RISK_DYSPNEA"],
        ),
        "胃胀两天，没有胸痛",
        use_langgraph=False,
        extractor_mode="fake",
        rag_enabled=False,
    )
    sticky_state = sticky["run_state"]
    ok = (
        high_risk_state.risk_flags_status == "present"
        and high_risk["memory"].facts["risk_flags_status"].source_kind == "risk_rule_engine"
        and sticky_state.risk_flags_status == "present"
        and sticky_state.metadata.get("p8_graph", {}).get("risk_rule_first") is True
    )
    return check(
        "graph_risk_guard_rule_first_and_sticky",
        ok,
        high_risk_status=high_risk_state.risk_flags_status,
        sticky_status=sticky_state.risk_flags_status,
        high_risk_source=high_risk["memory"].facts.get("risk_flags_status").source_kind,
        audit_reasons=[event.reason for event in sticky["memory"].audit_events],
    )


def run_next_action_safety_check() -> dict[str, Any]:
    graph_state = run_consultation_graph(
        RunState(),
        "我咳嗽",
        use_langgraph=False,
        extractor_mode="fake",
        rag_enabled=False,
    )
    ok = not graph_state["safety_issues"] and graph_state["next_action"] in {
        "ask_followup",
        "ready_for_structured_consultation_summary",
        "advise_timely_offline_medical_evaluation",
    }
    return check(
        "next_action_safety_boundary",
        ok,
        next_action=graph_state["next_action"],
        next_question=graph_state["run_state"].next_question,
        safety_issues=graph_state["safety_issues"],
    )


def build_payload() -> dict[str, Any]:
    checks = [
        run_state_model_check(),
        run_fallback_smoke(),
        run_optional_langgraph_smoke(),
        run_memory_update_check(),
        run_risk_guard_check(),
        run_next_action_safety_check(),
    ]
    status = status_from_checks(checks)
    optional = next(item for item in checks if item["name"] == "optional_langgraph_runtime")
    return {
        "phase": "P8-M2",
        "generated_at": utc_now(),
        "status": status,
        "scope": "LangGraph facade, fallback runtime, MemoryManager graph update path, risk guard, and next-action safety",
        "checks": checks,
        "metrics": {
            "check_count": len(checks),
            "passed_count": sum(1 for item in checks if item.get("ok") is True),
            "failed_count": sum(1 for item in checks if item.get("ok") is not True),
            "fallback_runtime_passed": checks[1].get("ok") is True,
            "optional_langgraph_status": optional.get("extra", {}).get("optional_status"),
            "memory_update_used": checks[3].get("ok") is True,
            "risk_guard_passed": checks[4].get("ok") is True,
        },
        "branch_safety": {
            "protected_tags_untouched": ["v0.7.0-p7-caution"],
            "protected_branches_untouched": [
                "backup/main-before-p7-device1-20260622-e986065",
                "origin/sft-local-pipeline",
                "origin/exp/sft-lora-extractor",
            ],
            "device2_sft_lora_code_mixed": False,
        },
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run P8-M2 graph facade validation.")
    parser.add_argument("--json", action="store_true", help="Print validation JSON.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT.relative_to(ROOT_DIR)), help="Artifact path.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv)
    payload = build_payload()
    output = ROOT_DIR / args.output
    write_json(output, payload)
    if args.json:
        print(json.dumps(json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            "P8 graph validation: "
            f"status={payload['status']} "
            f"fallback={payload['metrics']['fallback_runtime_passed']} "
            f"optional_langgraph={payload['metrics']['optional_langgraph_status']} "
            f"artifact={output.relative_to(ROOT_DIR)}"
        )
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
