from __future__ import annotations

from typing import Any, Protocol

from app.session.models import SessionRecord, TurnRecord


class SessionStore(Protocol):
    def create_session(self, session_id: str | None = None) -> SessionRecord:
        ...

    def append_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        turn_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TurnRecord:
        ...

    def save_state(self, session_id: str, state: Any) -> None:
        ...

    def load_state(self, session_id: str) -> dict[str, Any] | None:
        ...

    def list_turns(self, session_id: str) -> list[TurnRecord]:
        ...

    def save_event(self, session_id: str, event: dict[str, Any]) -> None:
        ...

    def export_session(self, session_id: str) -> dict[str, Any]:
        ...

    def replay_session(self, session_id: str) -> dict[str, Any]:
        ...

