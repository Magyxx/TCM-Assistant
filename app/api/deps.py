from __future__ import annotations

from app.storage.sqlite_store import P7SQLiteStore, get_default_store
from app.tools.registry import build_p7_registry


def get_p7_store() -> P7SQLiteStore:
    return get_default_store()


def get_p7_tools():
    return build_p7_registry()
