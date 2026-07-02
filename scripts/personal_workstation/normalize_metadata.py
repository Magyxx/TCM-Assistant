from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.personal_workstation.common import (  # noqa: E402
    MANAGED_TOP_LEVELS,
    WorkstationContext,
    frontmatter,
    make_context,
    markdown_files,
    read_frontmatter,
    stable_id,
    today_string,
    write_text_file,
)


def is_managed_note(ctx: WorkstationContext, path: Path) -> bool:
    try:
        rel = path.relative_to(ctx.target_root)
    except ValueError:
        return False
    return bool(rel.parts) and rel.parts[0] in MANAGED_TOP_LEVELS


def split_markdown(path: Path) -> tuple[dict[str, Any], list[str], str] | None:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith("---"):
        return {"type": "markdown-template" if "Templates" in path.parts else "markdown"}, [], text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    front = read_frontmatter(path)
    tags = front.pop("tags", [])
    if not isinstance(tags, list):
        tags = []
    body = parts[2].lstrip("\n")
    return front, [str(tag) for tag in tags], body


def infer_metadata(ctx: WorkstationContext, path: Path, front: dict[str, Any]) -> dict[str, Any]:
    note_type = str(front.get("type", "markdown"))
    today = today_string(ctx)
    front.setdefault("source", "personal_workstation.normalize_metadata")
    front.setdefault("preview", bool(ctx.config.get("preview_mode", True)))
    front.setdefault("human_review_required", True)
    front.setdefault("human_reviewed", False)
    front.setdefault("created", str(front.get("date") or front.get("period") or today))
    front.setdefault("updated", today)

    if note_type == "daily":
        date_text = str(front.get("date", path.stem))
        front.setdefault("id", stable_id("daily", date_text))
    elif note_type == "project":
        project = str(front.get("project", path.parent.name))
        front.setdefault("id", stable_id("project-note", f"{project}-{path.stem}"))
        front.setdefault("project_id", stable_id("project", project))
        front.setdefault("project_type", "general")
        front.setdefault("area", "workstation")
    elif note_type == "codex-task":
        project = str(front.get("project", "unknown"))
        task = str(front.get("task", path.stem))
        date_text = str(front.get("date", today))
        front.setdefault("id", stable_id("codex-task", f"{date_text}-{project}-{task}"))
        front.setdefault("project_id", stable_id("project", project))
    elif note_type == "knowledge-card":
        topic = str(front.get("topic", path.stem))
        front.setdefault("id", stable_id("knowledge", topic))
    elif note_type == "learning-note":
        date_text = str(front.get("date", today))
        area = str(front.get("area", path.parent.name))
        topic = str(front.get("topic", path.stem))
        front.setdefault("id", stable_id("learning-note", f"{date_text}-{area}-{topic}"))
    elif note_type == "document-log":
        date_text = str(front.get("date", today))
        title = str(front.get("title", path.stem))
        project = str(front.get("project", "none"))
        front.setdefault("id", stable_id("document-log", f"{date_text}-{project}-{title}"))
    elif note_type == "project-log":
        date_text = str(front.get("date", today))
        project = str(front.get("project", path.parent.parent.name if path.parent.name == "Logs" else "unknown"))
        title = str(front.get("title", path.stem))
        front.setdefault("id", stable_id("project-log", f"{date_text}-{project}-{title}"))
        front.setdefault("project_id", stable_id("project", project))
    elif note_type == "review":
        front.setdefault("id", stable_id("review", f"{front.get('review_type', 'review')}-{front.get('period', path.stem)}"))
    else:
        front.setdefault("id", stable_id(note_type, path.stem))
    return front


def normalize_metadata(ctx: WorkstationContext):
    results = []
    for path in markdown_files(ctx.target_root):
        if not is_managed_note(ctx, path):
            continue
        split = split_markdown(path)
        if split is None:
            continue
        front, tags, body = split
        updated = infer_metadata(ctx, path, front)
        results.append(write_text_file(path, frontmatter(updated, tags) + body, overwrite=True))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize Markdown frontmatter for Dataview/Bases readiness.")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    ctx = make_context(args.config)
    for result in normalize_metadata(ctx):
        print(f"{result.action}: {result.path}")


if __name__ == "__main__":
    main()
