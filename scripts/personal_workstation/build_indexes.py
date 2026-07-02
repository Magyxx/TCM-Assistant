from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.personal_workstation.common import (  # noqa: E402
    MANAGED_TOP_LEVELS,
    WorkstationContext,
    frontmatter,
    make_context,
    markdown_files,
    now_iso,
    read_frontmatter,
    relative_to_target,
    write_text_file,
)


def _table(headers: list[str], rows: list[list[str]]) -> str:
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    output.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(output) + "\n"


def _link(ctx: WorkstationContext, path: Path) -> str:
    rel = relative_to_target(ctx, path)
    return f"[[{rel}|{path.stem}]]"


def _is_managed_path(ctx: WorkstationContext, path: Path) -> bool:
    try:
        rel = path.relative_to(ctx.target_root)
    except ValueError:
        return False
    return bool(rel.parts) and rel.parts[0] in MANAGED_TOP_LEVELS


def index_frontmatter(name: str, ctx: WorkstationContext) -> str:
    return frontmatter(
        {
            "type": "system-index",
            "id": f"system-index-{name}",
            "index": name,
            "generated_at": now_iso(ctx),
            "source": "personal_workstation.build_indexes",
            "preview": bool(ctx.config.get("preview_mode", True)),
            "human_review_required": False,
            "human_reviewed": True,
            "created": now_iso(ctx),
            "updated": now_iso(ctx),
        },
        ["index", "workstation"],
    )


def project_index(ctx: WorkstationContext) -> str:
    root = ctx.target_root / str(ctx.config["projects_dir"])
    rows: list[list[str]] = []
    if root.exists():
        for current_status in sorted(root.rglob("Current_Status.md")):
            front = read_frontmatter(current_status)
            rows.append(
                [
                    front.get("project", current_status.parent.name),
                    front.get("status", "unknown"),
                    front.get("priority", "medium"),
                    front.get("stage", "unknown"),
                    _link(ctx, current_status),
                ]
            )
    return index_frontmatter("projects", ctx) + "# Project Index\n\n" + _table(
        ["Project", "Status", "Priority", "Stage", "Current Status"],
        rows or [["暂无", "-", "-", "-", "-"]],
    )


def codex_task_index(ctx: WorkstationContext) -> str:
    root = ctx.target_root / str(ctx.config["codex_tasks_dir"])
    rows = []
    for path in sorted(markdown_files(root), reverse=True):
        front = read_frontmatter(path)
        rows.append(
            [
                str(front.get("date", "")),
                str(front.get("project", "unknown")),
                str(front.get("task", path.stem)),
                str(front.get("verified", False)).lower(),
                str(front.get("risk", "unknown")),
                _link(ctx, path),
            ]
        )
    return index_frontmatter("codex-tasks", ctx) + "# Codex Task Index\n\n" + _table(
        ["Date", "Project", "Task", "Verified", "Risk", "Path"],
        rows or [["暂无", "-", "-", "-", "-", "-"]],
    )


def knowledge_index(ctx: WorkstationContext) -> str:
    root = ctx.target_root / str(ctx.config["knowledge_dir"])
    rows = []
    for path in sorted(markdown_files(root)):
        front = read_frontmatter(path)
        rows.append(
            [
                str(front.get("topic", path.stem)),
                str(front.get("domain", path.parent.name)),
                str(front.get("human_reviewed", False)).lower(),
                str(front.get("confidence", "unknown")),
                _link(ctx, path),
            ]
        )
    return index_frontmatter("knowledge", ctx) + "# Knowledge Index\n\n" + _table(
        ["Topic", "Domain", "Reviewed", "Confidence", "Path"],
        rows or [["暂无", "-", "-", "-", "-"]],
    )


def learning_index(ctx: WorkstationContext) -> str:
    root = ctx.target_root / "06_Learning"
    rows = []
    for path in sorted(markdown_files(root), reverse=True):
        front = read_frontmatter(path)
        if str(front.get("type", "")) not in {"learning-note", "agent-research-note"}:
            continue
        rows.append(
            [
                str(front.get("date", "")),
                str(front.get("area", path.parent.name)),
                str(front.get("topic", path.stem)),
                str(front.get("project", "none")),
                str(front.get("novelty") or front.get("status", "unknown")),
                _link(ctx, path),
            ]
        )
    return index_frontmatter("learning", ctx) + "# Learning Index\n\n" + _table(
        ["Date", "Area", "Topic", "Project", "Status", "Path"],
        rows or [["暂无", "-", "-", "-", "-", "-"]],
    )


def document_index(ctx: WorkstationContext) -> str:
    root = ctx.target_root / "08_Artifacts" / "Document_Logs"
    rows = []
    for path in sorted(markdown_files(root), reverse=True):
        front = read_frontmatter(path)
        rows.append(
            [
                str(front.get("date", "")),
                str(front.get("title", path.stem)),
                str(front.get("project", "none")),
                str(front.get("status", "unknown")),
                str(front.get("artifact_path", "none")),
                _link(ctx, path),
            ]
        )
    return index_frontmatter("documents", ctx) + "# Document Index\n\n" + _table(
        ["Date", "Title", "Project", "Status", "Artifact", "Path"],
        rows or [["暂无", "-", "-", "-", "-", "-"]],
    )


def project_log_index(ctx: WorkstationContext) -> str:
    root = ctx.target_root / str(ctx.config["projects_dir"])
    rows = []
    for path in sorted(markdown_files(root), reverse=True):
        front = read_frontmatter(path)
        if str(front.get("type", "")) != "project-log":
            continue
        rows.append(
            [
                str(front.get("date", "")),
                str(front.get("project", path.parent.parent.name if path.parent.name == "Logs" else "unknown")),
                str(front.get("title", path.stem)),
                str(front.get("category", "progress")),
                str(front.get("status", "unknown")),
                _link(ctx, path),
            ]
        )
    return index_frontmatter("project-logs", ctx) + "# Project Log Index\n\n" + _table(
        ["Date", "Project", "Title", "Category", "Status", "Path"],
        rows or [["暂无", "-", "-", "-", "-", "-"]],
    )


def review_index(ctx: WorkstationContext) -> str:
    root = ctx.target_root / str(ctx.config["reviews_dir"])
    rows = []
    for path in sorted(markdown_files(root), reverse=True):
        front = read_frontmatter(path)
        rows.append(
            [
                str(front.get("period", path.stem)),
                str(front.get("review_type", "unknown")),
                str(front.get("status", "unknown")),
                _link(ctx, path),
            ]
        )
    return index_frontmatter("reviews", ctx) + "# Review Index\n\n" + _table(
        ["Period", "Type", "Status", "Path"],
        rows or [["暂无", "-", "-", "-"]],
    )


def pending_review_index(ctx: WorkstationContext) -> str:
    rows = []
    for path in markdown_files(ctx.target_root):
        if not _is_managed_path(ctx, path):
            continue
        front = read_frontmatter(path)
        needs_review = front.get("human_review_required") is True or front.get("human_reviewed") is False
        if needs_review:
            rows.append(
                [
                    str(front.get("type", "markdown")),
                    str(front.get("project") or front.get("task") or front.get("topic") or path.stem),
                    str(front.get("status", "unknown")),
                    _link(ctx, path),
                ]
            )
    return index_frontmatter("pending-review", ctx) + "# Pending Review Index\n\n" + _table(
        ["Type", "Title", "Status", "Path"],
        rows or [["暂无", "-", "-", "-"]],
    )


def build_indexes(ctx: WorkstationContext):
    index_dir = ctx.target_root / "99_System" / "Indexes"
    specs = {
        "Project_Index.md": project_index(ctx),
        "Codex_Task_Index.md": codex_task_index(ctx),
        "Knowledge_Index.md": knowledge_index(ctx),
        "Learning_Index.md": learning_index(ctx),
        "Document_Index.md": document_index(ctx),
        "Project_Log_Index.md": project_log_index(ctx),
        "Review_Index.md": review_index(ctx),
        "Pending_Review_Index.md": pending_review_index(ctx),
    }
    results = []
    for name, content in specs.items():
        results.append(write_text_file(index_dir / name, content, overwrite=True))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Build generated workstation indexes.")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    ctx = make_context(args.config)
    for result in build_indexes(ctx):
        print(f"{result.action}: {result.path}")


if __name__ == "__main__":
    main()
