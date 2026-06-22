from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from app.observability.logger import append_jsonl, write_json


def export_trace_json(path: Path | str, payload: dict[str, Any]) -> None:
    write_json(path, payload)


def append_trace_jsonl(path: Path | str, events: Iterable[dict[str, Any]]) -> None:
    append_jsonl(path, events)
