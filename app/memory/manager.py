from __future__ import annotations

from typing import Any, Dict, List

from pydantic import ValidationError

from app.memory.experience_store import ExperienceStore
from app.memory.privacy import assert_l4_safe, preview_text
from app.memory.reducers import facts_from_run_state, source_traceability_pass
from app.memory.schemas import L1RecentTurn, MemorySnapshot
from app.memory.summary import summarize_from_facts
from app.schemas.report_schemas import RunState


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
