from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping

from pydantic import ValidationError

from app.memory.experience_store import ExperienceStore
from app.memory.audit import make_audit_event
from app.memory.merge_policy import merge_fact
from app.memory.models import (
    CANONICAL_FACT_FIELDS,
    L1RecentTurn as P8RecentTurn,
    ConsultationMemory,
    MemoryFact,
    canonical_fact_field,
    is_empty_value,
)
from app.memory.privacy import assert_l4_safe, preview_text
from app.memory.reducers import facts_from_run_state, source_traceability_pass
from app.memory.schemas import L1RecentTurn, MemorySnapshot
from app.memory.summary import build_case_summary, summarize_from_facts
from app.rules.rule_types import RiskEvaluation
from app.schemas.report_schemas import RunState, TurnOutput


TURN_OUTPUT_FACT_FIELDS = (
    "chief_complaint",
    "duration",
    "symptoms",
    "symptoms_status",
    "sleep",
    "appetite",
    "stool_urine",
    "risk_flags",
    "risk_flags_status",
)

RISK_EVALUATION_FIELDS = (
    "risk_flags_status",
    "risk_flags",
    "risk_reasons",
    "triggered_rule_ids",
)

NEGATION_MARKERS = (
    "no ",
    "not ",
    "denies",
    "without",
    "\u6ca1\u6709",
    "\u65e0",
    "\u5426\u8ba4",
    "\u672a\u89c1",
)


class MemoryManager:
    def __init__(self, max_recent_turns: int = 6, experience_store: ExperienceStore | None = None) -> None:
        self.max_recent_turns = max_recent_turns
        self.experience_store = experience_store or ExperienceStore()

    def _previous_recent_turns(self, previous_state: RunState) -> List[Dict[str, Any]]:
        memory = previous_state.metadata.get("p7_memory") if isinstance(previous_state.metadata, dict) else None
        if not isinstance(memory, dict):
            return []
        recent = memory.get("recent_turns")
        return recent if isinstance(recent, list) else []

    def build_snapshot(
        self,
        *,
        session_id: str,
        turn_id: str,
        turn_index: int,
        previous_state: RunState,
        current_state: RunState,
        user_input: str,
    ) -> MemorySnapshot:
        facts = facts_from_run_state(current_state, turn_id=turn_id, user_input=user_input)
        try:
            facts = [fact.model_copy(deep=True) for fact in facts]
        except ValidationError:
            facts = []
        recent_turns = [
            L1RecentTurn.model_validate(item)
            for item in self._previous_recent_turns(previous_state)
            if isinstance(item, dict)
        ]
        recent_turns.append(
            L1RecentTurn(
                turn_id=turn_id,
                turn_index=turn_index,
                user_input_preview=preview_text(user_input),
                risk_status=current_state.risk_flags_status,
            )
        )
        recent_turns = recent_turns[-self.max_recent_turns :]
        summary = summarize_from_facts(facts)
        l4_items = self.experience_store.retrieve(summary.summary, limit=3)
        l4_privacy_pass = assert_l4_safe([item.model_dump() for item in l4_items])
        return MemorySnapshot(
            session_id=session_id,
            turn_id=turn_id,
            recent_turns=recent_turns,
            structured_facts=facts,
            case_summary=summary,
            experience_retrieval=l4_items,
            source_traceability_pass=source_traceability_pass(facts),
            l4_privacy_pass=l4_privacy_pass,
            memory_write_pass=True,
        )

    def attach_snapshot(self, run_state: RunState, snapshot: MemorySnapshot) -> RunState:
        updated = run_state.model_copy(deep=True)
        updated.metadata = {
            **updated.metadata,
            "p7_memory": snapshot.model_dump(),
        }
        return updated

    def new_memory(self, *, session_id: str = "") -> ConsultationMemory:
        return ConsultationMemory(session_id=session_id)

    def from_run_state(
        self,
        run_state: RunState,
        *,
        session_id: str = "",
        turn_id: str = "run_state_bridge",
    ) -> ConsultationMemory:
        memory = ConsultationMemory(session_id=session_id)
        for field_name in CANONICAL_FACT_FIELDS:
            value = getattr(run_state, field_name, None)
            if is_empty_value(value):
                continue
            fact = MemoryFact(
                field_name=field_name,
                value=value,
                source_turn_id=turn_id,
                raw_text="",
                extractor_mode="run_state_bridge",
                confidence=1.0,
                source_kind="run_state_bridge",
            )
            memory.facts[field_name] = fact
        memory.case_summary = build_case_summary(memory)
        return memory

    def _coerce_memory(
        self,
        memory: ConsultationMemory | Mapping[str, Any] | None,
        previous_state: RunState | None,
        session_id: str,
    ) -> ConsultationMemory:
        if isinstance(memory, ConsultationMemory):
            return memory.model_copy(deep=True)
        if isinstance(memory, Mapping):
            return ConsultationMemory.model_validate(memory)

        if previous_state is not None:
            metadata_memory = (
                previous_state.metadata.get("p8_memory")
                if isinstance(previous_state.metadata, dict)
                else None
            )
            if isinstance(metadata_memory, Mapping):
                return ConsultationMemory.model_validate(metadata_memory)
            return self.from_run_state(previous_state, session_id=session_id)

        return self.new_memory(session_id=session_id)

    def _append_recent_turn(
        self,
        memory: ConsultationMemory,
        *,
        turn_id: str,
        turn_index: int,
        raw_text: str,
        extractor_mode: str,
    ) -> ConsultationMemory:
        updated = memory.model_copy(deep=True)
        updated.recent_turns.append(
            P8RecentTurn(
                turn_id=turn_id,
                turn_index=turn_index,
                raw_text_preview=preview_text(raw_text),
                extractor_mode=extractor_mode,
            )
        )
        updated.recent_turns = updated.recent_turns[-self.max_recent_turns :]
        return updated

    def _explicit_negation(self, value: Any, raw_text: str) -> bool:
        if value != "none":
            return False
        lowered = raw_text.lower()
        return any(marker in lowered for marker in NEGATION_MARKERS)

    def _explicit_correction_fields(self, values: Iterable[str] | None) -> set[str]:
        return {canonical_fact_field(value) for value in values or []}

    def _candidate_facts_from_turn_output(
        self,
        turn_output: TurnOutput,
        *,
        turn_id: str,
        raw_text: str,
        extractor_mode: str,
        confidence: float,
    ) -> list[MemoryFact]:
        facts: list[MemoryFact] = []
        for field_name in TURN_OUTPUT_FACT_FIELDS:
            value = getattr(turn_output, field_name)
            if is_empty_value(value):
                continue
            facts.append(
                MemoryFact(
                    field_name=field_name,
                    value=value,
                    source_turn_id=turn_id,
                    raw_text=raw_text,
                    extractor_mode=extractor_mode,
                    confidence=confidence,
                    source_kind="validated_turn_output",
                    explicit_negation=self._explicit_negation(value, raw_text),
                )
            )
        return facts

    def _risk_evaluation_payload(self, risk_evaluation: RiskEvaluation | Mapping[str, Any]) -> dict[str, Any]:
        if isinstance(risk_evaluation, RiskEvaluation):
            return {
                "risk_flags_status": risk_evaluation.risk_status,
                "risk_flags": list(risk_evaluation.risk_flags),
                "risk_reasons": list(risk_evaluation.risk_reasons),
                "triggered_rule_ids": list(risk_evaluation.triggered_rule_ids),
                "negated_rule_ids": list(risk_evaluation.negated_rule_ids),
            }
        payload = dict(risk_evaluation)
        if "risk_status" in payload and "risk_flags_status" not in payload:
            payload["risk_flags_status"] = payload["risk_status"]
        if "risk_rule_ids" in payload and "triggered_rule_ids" not in payload:
            payload["triggered_rule_ids"] = payload["risk_rule_ids"]
        return payload

    def _candidate_facts_from_risk_evaluation(
        self,
        risk_evaluation: RiskEvaluation | Mapping[str, Any] | None,
        *,
        turn_id: str,
        raw_text: str,
    ) -> list[MemoryFact]:
        if risk_evaluation is None:
            return []

        payload = self._risk_evaluation_payload(risk_evaluation)
        facts: list[MemoryFact] = []
        negated = bool(payload.get("negated_rule_ids"))
        for field_name in RISK_EVALUATION_FIELDS:
            value = payload.get(field_name)
            if is_empty_value(value):
                continue
            facts.append(
                MemoryFact(
                    field_name=field_name,
                    value=value,
                    source_turn_id=turn_id,
                    raw_text=raw_text,
                    extractor_mode="risk_rule_engine",
                    confidence=1.0,
                    source_kind="risk_rule_engine",
                    explicit_negation=negated and field_name == "risk_flags_status",
                )
            )
        return facts

    def apply_turn(
        self,
        *,
        memory: ConsultationMemory | Mapping[str, Any] | None = None,
        previous_state: RunState | None = None,
        turn_output: TurnOutput | Mapping[str, Any] | None = None,
        user_input: str = "",
        raw_text: str | None = None,
        turn_id: str = "",
        turn_index: int = 0,
        session_id: str = "",
        extractor_mode: str = "unknown",
        confidence: float = 0.85,
        risk_evaluation: RiskEvaluation | Mapping[str, Any] | None = None,
        explicit_corrections: Iterable[str] | None = None,
    ) -> ConsultationMemory:
        text = raw_text if raw_text is not None else user_input
        updated = self._coerce_memory(memory, previous_state, session_id)
        updated = self._append_recent_turn(
            updated,
            turn_id=turn_id,
            turn_index=turn_index,
            raw_text=text,
            extractor_mode=extractor_mode,
        )
        correction_fields = self._explicit_correction_fields(explicit_corrections)

        try:
            validated_turn = TurnOutput.model_validate(turn_output)
        except ValidationError as exc:
            updated.audit_events.append(
                make_audit_event(
                    turn_id=turn_id,
                    action="validate_turn_output",
                    applied=False,
                    reason=f"schema_validation_failed:{exc.__class__.__name__}",
                    extractor_mode=extractor_mode,
                )
            )
            updated.case_summary = build_case_summary(updated)
            return updated

        updated.audit_events.append(
            make_audit_event(
                turn_id=turn_id,
                action="validate_turn_output",
                applied=True,
                reason="schema_validation_passed",
                extractor_mode=extractor_mode,
            )
        )

        candidates = self._candidate_facts_from_turn_output(
            validated_turn,
            turn_id=turn_id,
            raw_text=text,
            extractor_mode=extractor_mode,
            confidence=confidence,
        )
        candidates.extend(
            self._candidate_facts_from_risk_evaluation(
                risk_evaluation,
                turn_id=turn_id,
                raw_text=text,
            )
        )

        for candidate in candidates:
            updated, _ = merge_fact(
                updated,
                candidate,
                explicit_correction=canonical_fact_field(candidate.field_name) in correction_fields,
            )

        updated.case_summary = build_case_summary(updated)
        return updated

    def export_run_state(self, memory: ConsultationMemory, base_state: RunState | None = None) -> RunState:
        state = (base_state or RunState()).model_copy(deep=True)
        for field_name, fact in memory.facts.items():
            canonical = canonical_fact_field(field_name)
            if hasattr(state, canonical):
                setattr(state, canonical, fact.value)
        state.summary = memory.case_summary.summary or state.summary
        state.metadata = {
            **state.metadata,
            "p8_memory": memory.model_dump(),
            "memory_schema_version": memory.schema_version,
            "memory_l3_generated_from_l2_only": memory.case_summary.generated_from_l2_only,
        }
        return state
