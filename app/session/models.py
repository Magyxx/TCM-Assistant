from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


Role = Literal["user", "assistant", "system", "tool"]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_session_id() -> str:
    return f"p9m2-{uuid4().hex[:12]}"


class TurnRecord(BaseModel):
    turn_id: str
    session_id: str
    role: Role
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)


class SessionRecord(BaseModel):
    session_id: str = Field(default_factory=new_session_id)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt-{uuid4().hex[:12]}")
    session_id: str
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)


class SessionExport(BaseModel):
    session: SessionRecord
    turns: list[TurnRecord] = Field(default_factory=list)
    state: dict[str, Any] | None = None
    events: list[SessionEvent] = Field(default_factory=list)

