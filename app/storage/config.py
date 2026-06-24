from __future__ import annotations

from pathlib import Path


DEFAULT_DATABASE_URL = "sqlite:///./artifacts/local_demo.db"


def sqlite_path_from_url(database_url: str = DEFAULT_DATABASE_URL) -> Path:
    if database_url.startswith("sqlite:///"):
        return Path(database_url.removeprefix("sqlite:///"))
    if database_url.startswith("sqlite://"):
        return Path(database_url.removeprefix("sqlite://"))
    raise ValueError("P1-F0 local demo storage only opens sqlite URLs")
