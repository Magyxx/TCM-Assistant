from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from p7_common import json_safe, write_json
except ImportError:  # pragma: no cover
    from scripts.p7_common import json_safe, write_json

from app.graph.consultation_graph import NODE_SEQUENCE, run_consultation_graph
from app.graph.runtime import is_langgraph_available
from app.graph.state import ConsultationGraphState
from app.memory.merge_policy import merge_fact
from app.memory.models import ConsultationMemory, MemoryFact
from app.rules.risk_rules import RISK_RULES
from app.schemas.report_schemas import RunState
from app.storage.models import utc_now


DEFAULT_OUTPUT = ROOT_DIR / "artifacts" / "p8_graph_validation.json"
EXPECTED_NODE_SEQUENCE = [
    "normalize_input",
    "extract_turn",
    "validate_turn",
    "memory_update",
    "risk_check",
    "plan_next_action",
]


def _git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT_DIR, text=True).strip()
    except Exception:
        return "unknown"


def _status(value: bool) -> str:
    return "passed" if value else "failed"


def graph_state_schema_passed() -> bool:
    try:
        state = ConsultationGraphState(
            session_id="verify-session",
            turn_id="turn-1",
            user_input="stomach discomfort",
        )
        replayed = ConsultationGraphState.model_validate(state.model_dump())
        try:
            ConsultationGraphState.model_validate({"session_id": "missing-turn", "user_input": "x"})
            required_fields_fail = False
        except Exception:
            required_fields_fail = True
        return replayed.session_id == "verify-session" and required_fields_fail
    except Exception:
        return False


def fallback_turn_smoke() -> dict[str, Any]:
    graph_state = run_consultation_graph(
        RunState(),
        "胃胀一周，饭后明显",
        use_langgraph=False,
        extractor_mode="fake",
        rag_enabled=False,
    )
    run_state = graph_state["run_state"]
    memory = graph_state["memory"]
    return {
        "passed": (
            graph_state["graph_runtime"] == "sequential_fallback"
            and [name for name, _ in NODE_SEQUENCE] == EXPECTED_NODE_SEQUENCE
            and memory.fact_value("chief_complaint") == "胃胀"
            and memory.fact_value("duration") == "一周"
            and run_state.chief_complaint == "胃胀"
            and run_state.duration == "一周"
        ),
        "graph_state": graph_state,
    }


def optional_langgraph_status() -> str:
    if not is_langgraph_available():
        return "skipped"
    graph_state = run_consultation_graph(
        RunState(),
        "stomach discomfort for two days",
        use_langgraph=True,
        extractor_mode="fake",
        rag_enabled=False,
    )
    return "passed" if graph_state["graph_runtime"] == "langgraph" else "failed"


def risk_guard_passed() -> dict[str, bool]:
    high_risk = run_consultation_graph(
        RunState(),
        RISK_RULES[0].trigger_keywords[0],
        use_langgraph=False,
        extractor_mode="fallback",
        rag_enabled=False,
    )
    sticky = run_consultation_graph(
        RunState(
            chief_complaint="chest tightness",
            duration="one day",
            symptoms_status="unknown",
            risk_flags_status="present",
            risk_flags=["dyspnea"],
            triggered_rule_ids=["P0_RISK_DYSPNEA"],
        ),
        "stomach discomfort for two days, no chest pain",
        use_langgraph=False,
        extractor_mode="fake",
        rag_enabled=False,
    )
    memory = ConsultationMemory(session_id="rag-guard")
    memory.facts["chief_complaint"] = MemoryFact(
        field_name="chief_complaint",
        value="胃胀",
        source_turn_id="turn-1",
        source_kind="validated_turn_output",
    )
    blocked_memory, event = merge_fact(
        memory,
        MemoryFact(
            field_name="chief_complaint",
            value="RAG override attempt",
            source_turn_id="rag-1",
            source_kind="rag_evidence",
        ),
    )
    return {
        "llm_risk_overwrite_blocked": any(
            event.reason == "llm_candidate_cannot_write_risk_authority"
            for event in sticky["memory"].audit_events
        ),
        "high_risk_present_sticky": sticky["run_state"].risk_flags_status == "present",
        "rag_core_field_overwrite_blocked": (
            event.reason == "rag_evidence_forbidden_for_core_field"
            and blocked_memory.fact_value("chief_complaint") == "胃胀"
        ),
        "risk_rule_authority": (
            high_risk["run_state"].risk_flags_status == "present"
            and high_risk["memory"].facts["risk_flags_status"].source_kind == "risk_rule_engine"
        ),
    }


def build_payload() -> dict[str, Any]:
    fallback = fallback_turn_smoke()
    graph_state = fallback["graph_state"]
    memory = graph_state["memory"]
    run_state = graph_state["run_state"]
    langgraph_status = optional_langgraph_status()
    safety = risk_guard_passed()
    checks = {
        "graph_state_schema": _status(graph_state_schema_passed()),
        "fallback_turn_smoke": _status(bool(fallback["passed"])),
        "memory_manager_invoked": _status(bool(run_state.metadata.get("p8_graph", {}).get("memory_update_used"))),
        "run_state_export": _status(run_state.chief_complaint == "胃胀" and "p8_memory" in run_state.metadata),
        "risk_guard": _status(all(safety.values())),
        "audit_events": _status(bool(memory.audit_events) and bool(graph_state["audit_events"])),
    }
    status = "ok" if all(value == "passed" for value in checks.values()) and langgraph_status != "failed" else "failed"
    return {
        "stage": "P8-M2_LANGGRAPH_FACADE",
        "status": status,
        "generated_at": utc_now(),
        "branch": _git(["branch", "--show-current"]),
        "commit": _git(["rev-parse", "--short", "HEAD"]),
        "runtime": {
            "fallback": "passed" if fallback["passed"] else "failed",
            "langgraph": langgraph_status,
            "langgraph_installed": is_langgraph_available(),
        },
        "checks": checks,
        "safety": {
            "llm_risk_overwrite_blocked": safety["llm_risk_overwrite_blocked"],
            "high_risk_present_sticky": safety["high_risk_present_sticky"],
            "rag_core_field_overwrite_blocked": safety["rag_core_field_overwrite_blocked"],
            "risk_rule_authority": safety["risk_rule_authority"],
        },
        "graph": {
            "node_sequence": [name for name, _ in NODE_SEQUENCE],
            "memory_fact_fields": sorted(memory.facts.keys()),
            "audit_event_count": len(graph_state["audit_events"]),
        },
        "device2_lora_branch": {
            "status": "external_branch_only",
            "merged_training_artifacts": False,
            "merged_model_weights": False,
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
            f"fallback={payload['runtime']['fallback']} "
            f"langgraph={payload['runtime']['langgraph']} "
            f"artifact={output.relative_to(ROOT_DIR)}"
        )
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
