from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from app.api.redaction import redact_secret_text
from app.schemas.report_schemas import RunState


TRACKED_FIELDS = (
    "chief_complaint",
    "duration",
    "symptoms",
    "symptoms_status",
    "risk_flags",
    "risk_flags_status",
    "risk_reasons",
    "triggered_rule_ids",
)


class ConsultationMemorySnapshot(BaseModel):
    phase: str = "P4.2"
    memory_type: str = "consultation_safety_memory"
    is_user_profile: bool = False
    l1_recent_turns: List[Dict[str, Any]] = Field(default_factory=list)
    l2_authoritative_state: Dict[str, Any] = Field(default_factory=dict)
    l3_consultation_summary: Dict[str, Any] = Field(default_factory=dict)
    l4_long_term_memory: Dict[str, Any] = Field(default_factory=dict)
    field_sources: Dict[str, str] = Field(default_factory=dict)
    high_risk_sticky: bool = True
    negation_tracking: Dict[str, Any] = Field(default_factory=dict)
    trace: List[Dict[str, Any]] = Field(default_factory=list)


class ConsultationMemoryManager:
    """Bounded memory that annotates state continuity without becoming state authority."""

    def __init__(self, max_recent_turns: int = 6) -> None:
        self.max_recent_turns = max_recent_turns

    def enforce_high_risk_sticky(self, previous_state: RunState, candidate_state: RunState) -> RunState:
        if previous_state.risk_flags_status != "present":
            return candidate_state
        if candidate_state.risk_flags_status == "present":
            return candidate_state

        protected = candidate_state.model_copy(deep=True)
        protected.risk_flags_status = "present"
        protected.risk_flags = list(dict.fromkeys(previous_state.risk_flags + protected.risk_flags))
        protected.risk_reasons = list(dict.fromkeys(previous_state.risk_reasons + protected.risk_reasons))
        protected.triggered_rule_ids = list(
            dict.fromkeys(previous_state.triggered_rule_ids + protected.triggered_rule_ids)
        )
        protected.metadata = {
            **protected.metadata,
            "p4_memory_high_risk_sticky_applied": True,
        }
        return protected

    def _recent_turns(self, previous_state: RunState, user_input: str, current_state: RunState) -> List[Dict[str, Any]]:
        previous_memory = previous_state.metadata.get("p4_memory") if isinstance(previous_state.metadata, dict) else None
        recent = []
        if isinstance(previous_memory, dict):
            recent = list(previous_memory.get("l1_recent_turns") or [])
        preview = redact_secret_text(str(user_input)).strip()
        if len(preview) > 120:
            preview = f"{preview[:120]}...[TRUNCATED]"
        recent.append(
            {
                "turn_count": current_state.turn_count,
                "user_input_preview": preview,
                "risk_flags_status": current_state.risk_flags_status,
            }
        )
        return recent[-self.max_recent_turns :]

    def _field_sources(self, previous_state: RunState, current_state: RunState) -> Dict[str, str]:
        sources: Dict[str, str] = {}
        for field in TRACKED_FIELDS:
            previous = getattr(previous_state, field)
            current = getattr(current_state, field)
            if field in {"risk_flags_status", "risk_flags", "risk_reasons", "triggered_rule_ids"}:
                sources[field] = "risk_rule_node" if current else "not_available"
            elif current in (None, [], "unknown"):
                sources[field] = "not_available"
            elif previous == current:
                sources[field] = "previous_authoritative_state"
            else:
                sources[field] = "current_turn_validated_extraction"
        return sources

    def update(
        self,
        *,
        previous_state: RunState,
        current_state: RunState,
        user_input: str,
        trace: List[Dict[str, Any]] | None = None,
    ) -> ConsultationMemorySnapshot:
        last_risk_eval = current_state.metadata.get("last_risk_rule_eval") if isinstance(current_state.metadata, dict) else {}
        if not isinstance(last_risk_eval, dict):
            last_risk_eval = {}

        field_sources = self._field_sources(previous_state, current_state)
        l2_state = {
            "authoritative": True,
            "state_model": "RunState",
            "turn_count": current_state.turn_count,
            "field_presence": {
                "chief_complaint": bool(current_state.chief_complaint),
                "duration": bool(current_state.duration),
                "symptoms_status": current_state.symptoms_status,
                "risk_flags_status": current_state.risk_flags_status,
                "triggered_rule_ids": list(current_state.triggered_rule_ids),
            },
        }
        l3_summary = {
            "summary_available": bool(current_state.summary),
            "final_report_available": current_state.final_report is not None,
            "followup_needed": bool(current_state.next_question),
            "field_sources_available": True,
        }
        l4_memory = {
            "contains_raw_patient_pii": False,
            "contains_user_profile": False,
            "stored_items": [],
            "allowed_content": "knowledge_or_anonymized_eval_experience_only",
        }
        return ConsultationMemorySnapshot(
            l1_recent_turns=self._recent_turns(previous_state, user_input, current_state),
            l2_authoritative_state=l2_state,
            l3_consultation_summary=l3_summary,
            l4_long_term_memory=l4_memory,
            field_sources=field_sources,
            negation_tracking={
                "negated_rule_ids": list(last_risk_eval.get("negated_rule_ids") or []),
                "explicit": bool(last_risk_eval.get("negated_rule_ids")),
            },
            trace=list(trace or []),
        )

