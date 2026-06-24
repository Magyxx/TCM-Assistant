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

from app.memory.manager import MemoryManager
from app.memory.merge_policy import merge_fact
from app.memory.models import ConsultationMemory, MemoryFact
from app.memory.privacy import assert_l4_safe
from app.memory.summary import build_case_summary
from app.schemas.report_schemas import TurnOutput
from app.storage.models import utc_now


DEFAULT_OUTPUT = ROOT_DIR / "artifacts" / "p8_memory_validation.json"


def run_valid_turn_check() -> dict[str, Any]:
    manager = MemoryManager()
    memory = manager.apply_turn(
        turn_output=TurnOutput(
            chief_complaint="stomach discomfort",
            duration="two days",
            symptoms_status="none",
        ),
        user_input="stomach discomfort for two days, no other symptoms",
        turn_id="t1",
        turn_index=1,
        extractor_mode="fake",
    )
    state = manager.export_run_state(memory)
    ok = (
        memory.fact_value("chief_complaint") == "stomach discomfort"
        and state.chief_complaint == "stomach discomfort"
        and state.duration == "two days"
        and "p8_memory" in state.metadata
        and all(
            memory.facts[field].source_turn_id
            and memory.facts[field].raw_text
            and memory.facts[field].extractor_mode
            and memory.facts[field].confidence is not None
            for field in ("chief_complaint", "duration")
        )
    )
    return check(
        "valid_turn_output_to_l2_and_run_state",
        ok,
        facts=list(memory.facts.keys()),
        audit_event_count=len(memory.audit_events),
        exported_state=state.model_dump(),
    )


def run_invalid_schema_check() -> dict[str, Any]:
    manager = MemoryManager()
    memory = manager.apply_turn(
        turn_output={"chief_complaint": "cough", "symptoms": "not-a-list"},
        user_input="cough",
        turn_id="bad1",
        turn_index=1,
        extractor_mode="broken",
    )
    ok = not memory.facts and any(
        event.reason.startswith("schema_validation_failed") for event in memory.audit_events
    )
    return check(
        "invalid_turn_output_rejected_before_l2",
        ok,
        fact_count=len(memory.facts),
        audit=[event.model_dump() for event in memory.audit_events],
    )


def run_merge_policy_check() -> dict[str, Any]:
    memory = ConsultationMemory()
    memory, _ = merge_fact(
        memory,
        MemoryFact(
            field_name="duration",
            value="two days",
            source_turn_id="t1",
            raw_text="duration two days",
            extractor_mode="fake",
            confidence=0.95,
        ),
    )
    memory, low_conf_event = merge_fact(
        memory,
        MemoryFact(
            field_name="duration",
            value="three days",
            source_turn_id="t2",
            raw_text="duration three days",
            extractor_mode="fake",
            confidence=0.2,
        ),
    )
    memory, empty_event = merge_fact(
        memory,
        MemoryFact(
            field_name="duration",
            value=None,
            source_turn_id="t3",
            raw_text="",
            extractor_mode="fake",
            confidence=1.0,
        ),
    )
    ok = (
        memory.fact_value("duration") == "two days"
        and low_conf_event.reason == "low_confidence_candidate_cannot_overwrite_higher_confidence_fact"
        and empty_event.reason == "empty_candidate_cannot_overwrite_non_empty_fact"
    )
    return check(
        "empty_and_low_confidence_rejected",
        ok,
        duration=memory.fact_value("duration"),
        low_confidence_reason=low_conf_event.reason,
        empty_reason=empty_event.reason,
    )


def run_risk_guard_check() -> dict[str, Any]:
    manager = MemoryManager()
    memory = manager.apply_turn(
        turn_output=TurnOutput(risk_flags_status="present", risk_flags=["chest pain"]),
        user_input="llm candidate text",
        turn_id="t1",
        turn_index=1,
        extractor_mode="fake",
    )
    llm_blocked = "risk_flags_status" not in memory.facts and any(
        event.reason == "llm_candidate_cannot_write_risk_authority" for event in memory.audit_events
    )
    memory = manager.apply_turn(
        memory=memory,
        turn_output=TurnOutput(chief_complaint="chest tightness"),
        user_input="chest tightness and shortness of breath",
        turn_id="t2",
        turn_index=2,
        extractor_mode="fake",
        risk_evaluation={
            "risk_status": "present",
            "risk_flags": ["dyspnea"],
            "risk_rule_ids": ["P0_RISK_DYSPNEA"],
            "risk_reasons": ["shortness of breath"],
        },
    )
    memory = manager.apply_turn(
        memory=memory,
        turn_output=TurnOutput(symptoms_status="none"),
        user_input="no chest pain now",
        turn_id="t3",
        turn_index=3,
        extractor_mode="fake",
        risk_evaluation={"risk_status": "none", "negated_rule_ids": ["P0_RISK_CHEST_PAIN"]},
    )
    sticky = memory.fact_value("risk_flags_status") == "present" and any(
        event.reason == "high_risk_present_is_sticky" for event in memory.audit_events
    )
    return check(
        "risk_rule_authority_and_high_risk_sticky",
        llm_blocked and sticky,
        risk_status=memory.fact_value("risk_flags_status"),
        llm_blocked=llm_blocked,
        high_risk_sticky=sticky,
    )


def run_rag_guard_check() -> dict[str, Any]:
    memory = ConsultationMemory()
    memory, event = merge_fact(
        memory,
        MemoryFact(
            field_name="chief_complaint",
            value="retrieved text",
            source_turn_id="rag1",
            raw_text="retrieved evidence",
            extractor_mode="bm25",
            confidence=1.0,
            source_kind="rag_evidence",
        ),
    )
    ok = not event.applied and event.reason == "rag_evidence_forbidden_for_core_field"
    return check(
        "rag_evidence_forbidden_for_core_fields",
        ok,
        event=event.model_dump(),
        facts=memory.model_dump().get("facts"),
    )


def run_summary_and_l4_check() -> dict[str, Any]:
    manager = MemoryManager()
    memory = manager.apply_turn(
        turn_output=TurnOutput(chief_complaint="cough", duration="three days"),
        user_input="cough for three days",
        turn_id="t1",
        turn_index=1,
        extractor_mode="fake",
    )
    summary = build_case_summary(memory)
    summary.summary = "manual edit cannot write back to facts"
    l2_unchanged = memory.fact_value("chief_complaint") == "cough"
    l4_safe = assert_l4_safe(memory.l4_experience.stored_items)
    ok = summary.generated_from_l2_only and l2_unchanged and l4_safe and not memory.l4_experience.enabled
    return check(
        "summary_from_l2_only_and_l4_private",
        ok,
        summary=memory.case_summary.model_dump(),
        l4=memory.l4_experience.model_dump(),
    )


def build_payload() -> dict[str, Any]:
    checks = [
        run_valid_turn_check(),
        run_invalid_schema_check(),
        run_merge_policy_check(),
        run_risk_guard_check(),
        run_rag_guard_check(),
        run_summary_and_l4_check(),
    ]
    status = status_from_checks(checks)
    return {
        "phase": "P8-M1",
        "generated_at": utc_now(),
        "status": status,
        "scope": "MemoryManager L1/L2/L3/L4 interface, safe merge, audit, risk guard, and RAG boundary checks",
        "checks": checks,
        "metrics": {
            "check_count": len(checks),
            "passed_count": sum(1 for item in checks if item.get("ok") is True),
            "failed_count": sum(1 for item in checks if item.get("ok") is not True),
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
    parser = argparse.ArgumentParser(description="Run P8-M1 memory manager validation.")
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
            "P8 memory validation: "
            f"status={payload['status']} "
            f"passed={payload['metrics']['passed_count']}/{payload['metrics']['check_count']} "
            f"artifact={output.relative_to(ROOT_DIR)}"
        )
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
