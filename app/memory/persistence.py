from __future__ import annotations

from app.memory.schemas import MemorySnapshot
from app.storage.models import MemorySnapshotRecord
from app.storage.sqlite_store import P7SQLiteStore


def persist_memory_snapshot(store: P7SQLiteStore, snapshot: MemorySnapshot) -> MemorySnapshotRecord:
    record = MemorySnapshotRecord(
        session_id=snapshot.session_id,
        turn_id=snapshot.turn_id,
        snapshot=snapshot.model_dump(),
    )
    return record
