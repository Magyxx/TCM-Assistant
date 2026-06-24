from __future__ import annotations

from app.schemas.report_schemas import RunState
from app.session.memory_store import MemorySessionStore
from app.session.sqlite_store import SQLiteSessionStore


def exercise_store(store) -> None:
    session = store.create_session("store-test")
    store.append_turn(session.session_id, "user", "胃胀一周", turn_id="turn-1")
    store.save_state(session.session_id, RunState(chief_complaint="胃胀", duration="一周"))
    store.save_event(session.session_id, {"event_type": "graph_event", "node": "test"})
    exported = store.export_session(session.session_id)
    replayed = store.replay_session(session.session_id)

    assert exported["state"]["chief_complaint"] == "胃胀"
    assert exported["turns"][0]["content"] == "胃胀一周"
    assert replayed["replayed_state"]["duration"] == "一周"


def test_memory_session_store_roundtrip() -> None:
    exercise_store(MemorySessionStore())


def test_sqlite_session_store_roundtrip(tmp_path) -> None:
    exercise_store(SQLiteSessionStore(tmp_path / "sessions.sqlite3"))
