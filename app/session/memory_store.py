from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.session.models import SessionEvent, SessionRecord, TurnRecord, utc_now


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


class MemorySessionStore:
    def __init__(self) -> None:
        self.sessions: dict[str, SessionRecord] = {}
        self.turns: dict[str, list[TurnRecord]] = {}
        self.states: dict[str, dict[str, Any]] = {}
        self.events: dict[str, list[SessionEvent]] = {}

    def create_session(self, session_id: str | None = None) -> SessionRecord:
        record = self.sessions.get(session_id or "")
        if record is not None:
            return record
        record = SessionRecord(session_id=session_id or f"p9m2-{uuid4().hex[:12]}")
        self.sessions[record.session_id] = record
        self.turns.setdefault(record.session_id, [])
        self.events.setdefault(record.session_id, [])
        return record

    def append_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        turn_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TurnRecord:
        self.create_session(session_id)
        record = TurnRecord(
            session_id=session_id,
            turn_id=turn_id or f"turn-{len(self.turns[session_id]) + 1}",
            role=role,  # type: ignore[arg-type]
            content=content,
            metadata=metadata or {},
        )
        self.turns[session_id].append(record)
        self.sessions[session_id].updated_at = utc_now()
        return record

    def save_state(self, session_id: str, state: Any) -> None:
        self.create_session(session_id)
        self.states[session_id] = _jsonable(state)
        self.sessions[session_id].updated_at = utc_now()

    def load_state(self, session_id: str) -> dict[str, Any] | None:
        return self.states.get(session_id)

    def list_turns(self, session_id: str) -> list[TurnRecord]:
        return list(self.turns.get(session_id, []))

    def save_event(self, session_id: str, event: dict[str, Any]) -> None:
        self.create_session(session_id)
        payload = dict(event)
        event_type = str(payload.pop("event_type", payload.get("node", "event")))
        self.events[session_id].append(SessionEvent(session_id=session_id, event_type=event_type, payload=_jsonable(payload)))

    def export_session(self, session_id: str) -> dict[str, Any]:
        session = self.create_session(session_id)
        return {
            "session": session.model_dump(),
            "turns": [turn.model_dump() for turn in self.list_turns(session_id)],
            "state": self.load_state(session_id),
            "events": [event.model_dump() for event in self.events.get(session_id, [])],
        }

    def replay_session(self, session_id: str) -> dict[str, Any]:
        export = self.export_session(session_id)
        export["replayed_state"] = export.get("state")
        export["replay_turn_count"] = len(export.get("turns") or [])
        return export

