from __future__ import annotations

import re
from typing import List

from app.chains.turn_extractor import extract_turn
from app.graph.state import ConsultationGraphState
from app.memory.manager import MemoryManager
from app.rules.risk_rules import evaluate_risk_rules
from app.schemas.report_schemas import RunState, TurnOutput


FORBIDDEN_NEXT_ACTION_TERMS = (
    "diagnose",
    "diagnosis",
    "prescribe",
    "prescription",
    "replace doctor",
)


def _missing_core_fields(run_state: RunState) -> List[str]:
    missing: list[str] = []
    if not run_state.chief_complaint:
        missing.append("chief_complaint")
    if not run_state.duration:
        missing.append("duration")
    if run_state.symptoms_status == "unknown":
        missing.append("symptoms_status")
    if run_state.risk_flags_status == "unknown":
        missing.append("risk_flags_status")
    return missing


def _safe_followup_question(run_state: RunState) -> str | None:
    if run_state.risk_flags_status == "present":
        return None
    if not run_state.chief_complaint:
        return "Please describe the main discomfort you want to organize first."
    if not run_state.duration:
        return "How long has this main discomfort been present?"
    if run_state.symptoms_status == "unknown":
        return "Are there any accompanying symptoms? If not, please say none."
    if run_state.risk_flags_status == "unknown":
        return "Are there risk signals such as chest pain, breathing difficulty, persistent high fever, bleeding, confusion, or sudden severe worsening?"
    return None


def _record_safety_issues(text: str) -> list[str]:
    lowered = text.lower()
    return [term for term in FORBIDDEN_NEXT_ACTION_TERMS if term in lowered]


def normalize_input(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    updated.normalized_input = re.sub(r"\s+", " ", updated.user_input).strip()
    updated.metrics["normalize_input"] = "ok"
    return updated


def extract_turn_node(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    user_input = updated.normalized_input or updated.user_input
    result = extract_turn(
        updated.run_state,
        user_input,
        extractor_mode=updated.extractor_mode_requested,
    )
    updated.turn_output = result.turn_output
    updated.extraction_result = result.to_dict()
    updated.extraction_mode = result.mode
    updated.extractor_mode = result.extractor_mode or result.mode
    updated.strategy = result.strategy
    updated.model_name = result.model_name
    updated.error_type = result.error_type
    updated.error_message_preview = result.error_message_preview
    updated.json_valid = result.json_valid
    updated.schema_valid = result.schema_valid
    updated.raw_llm_json_valid = result.raw_llm_json_valid
    updated.final_schema_pass = result.final_schema_pass
    updated.fallback_used = result.fallback_used
    updated.metrics["extract_turn"] = result.mode
    if result.error:
        updated.errors.append(result.error)
    return updated


def validate_turn(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    try:
        updated.turn_output = TurnOutput.model_validate(updated.turn_output)
        updated.schema_valid = True
        updated.metrics["validate_turn"] = "ok"
    except Exception as exc:
        updated.turn_output = None
        updated.schema_valid = False
        updated.errors.append(f"turn_output_schema_invalid:{exc.__class__.__name__}")
        updated.metrics["validate_turn"] = "failed"
    return updated


def memory_update(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    manager = MemoryManager()
    user_input = updated.normalized_input or updated.user_input
    next_turn_count = updated.run_state.turn_count + 1
    updated.memory = manager.apply_turn(
        memory=updated.memory,
        previous_state=updated.run_state,
        turn_output=updated.turn_output,
        user_input=user_input,
        raw_text=user_input,
        turn_id=f"turn-{next_turn_count}",
        turn_index=next_turn_count,
        extractor_mode=updated.extractor_mode or updated.extractor_mode_requested,
    )
    exported = manager.export_run_state(updated.memory, base_state=updated.run_state)
    exported.turn_count = next_turn_count
    updated.run_state = exported
    updated.metrics["memory_update"] = "ok"
    return updated


def risk_check(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    manager = MemoryManager()
    user_input = updated.normalized_input or updated.user_input
    evaluation = evaluate_risk_rules(user_input, previous_status=updated.run_state.risk_flags_status)
    updated.memory = manager.apply_risk_evaluation(
        memory=updated.memory,
        risk_evaluation=evaluation,
        turn_id=f"turn-{updated.run_state.turn_count}",
        raw_text=user_input,
    )
    exported = manager.export_run_state(updated.memory, base_state=updated.run_state)
    exported.turn_count = updated.run_state.turn_count
    exported.metadata = {
        **exported.metadata,
        "last_risk_rule_eval": {
            "risk_status": evaluation.risk_status,
            "triggered_rule_ids": list(evaluation.triggered_rule_ids),
            "negated_rule_ids": list(evaluation.negated_rule_ids),
            "risk_reasons": list(evaluation.risk_reasons),
        },
    }
    updated.run_state = exported
    updated.risk_status = updated.run_state.risk_flags_status
    updated.risk_reasons = list(updated.run_state.risk_reasons)
    updated.triggered_rule_ids = list(updated.run_state.triggered_rule_ids)
    updated.metrics["risk_check"] = "ok"
    return updated


def plan_next_action(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    run_state = updated.run_state.model_copy(deep=True)
    missing = _missing_core_fields(run_state)
    updated.missing_core_fields = missing

    if run_state.risk_flags_status == "present":
        run_state.next_question = None
        updated.next_action = "advise_timely_offline_medical_evaluation"
        updated.done = True
    elif missing:
        run_state.next_question = _safe_followup_question(run_state)
        updated.next_action = "ask_followup"
        updated.done = False
    else:
        run_state.next_question = None
        updated.next_action = "ready_for_structured_consultation_summary"
        updated.done = True

    updated.safety_issues = _record_safety_issues(" ".join([updated.next_action, run_state.next_question or ""]))
    updated.run_state = run_state
    updated.metrics["plan_next_action"] = "ok"
    return updated

__all__ = [
    "extract_turn_node",
    "memory_update",
    "normalize_input",
    "plan_next_action",
    "risk_check",
    "validate_turn",
]
