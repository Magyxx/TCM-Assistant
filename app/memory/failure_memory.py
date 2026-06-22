from __future__ import annotations

import json
from pathlib import Path

from app.memory.experience import ExperienceMemory


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_FAILURE_MEMORY_PATH = ROOT_DIR / "knowledge" / "processed" / "failure_memory.jsonl"


def load_failure_memory(path: Path = DEFAULT_FAILURE_MEMORY_PATH) -> list[ExperienceMemory]:
    if not path.exists():
        return []
    rows: list[ExperienceMemory] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.strip():
            rows.append(ExperienceMemory.model_validate(json.loads(line)))
    return rows


def write_failure_memory(rows: list[ExperienceMemory], path: Path = DEFAULT_FAILURE_MEMORY_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row.model_dump(), ensure_ascii=False, sort_keys=True) + "\n")
    return path

