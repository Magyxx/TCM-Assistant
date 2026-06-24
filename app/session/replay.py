from __future__ import annotations

from app.session.sqlite_store import SQLiteSessionStore
from app.session.store import SessionStore


def replay_session(session_id: str, store: SessionStore | None = None) -> dict:
    store = store or SQLiteSessionStore()
    return store.replay_session(session_id)

