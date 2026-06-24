from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from app.observability.events import GraphEvent, sanitize_event


DEFAULT_GRAPH_EVENTS_PATH = Path("artifacts/p9m2/graph_events.jsonl")


def append_graph_events(events: Iterable[GraphEvent | dict], path: str | Path = DEFAULT_GRAPH_EVENTS_PATH) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for event in events:
            payload = event.model_dump() if hasattr(event, "model_dump") else dict(event)
            handle.write(json.dumps(sanitize_event(payload), ensure_ascii=False, sort_keys=True) + "\n")
    return path


def json_event_line(event: Any) -> str:
    payload = event.model_dump() if hasattr(event, "model_dump") else dict(event)
    return json.dumps(sanitize_event(payload), ensure_ascii=False, sort_keys=True)


def append_json_event(event: Any, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json_event_line(event) + "\n")
    return path


def read_graph_events(path: str | Path = DEFAULT_GRAPH_EVENTS_PATH) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    events = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                events.append(json.loads(line))
    return events
