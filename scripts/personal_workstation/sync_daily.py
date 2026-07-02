from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.personal_workstation.common import (  # noqa: E402
    WorkstationContext,
    configured_path,
    make_context,
    markdown_files,
    read_frontmatter,
    relative_to_target,
    today_string,
    write_text_file,
)
from scripts.personal_workstation.write_daily_note import create_daily_note  # noqa: E402


DAILY_SYNC_MARKER = "PERSONAL_WORKSTATION_DAILY_SYNC"


def remove_marked_section(text: str, marker: str) -> str:
    start = f"<!-- BEGIN {marker} -->"
    end = f"<!-- END {marker} -->"
    pattern = re.compile(r"\n?" + re.escape(start) + r".*?" + re.escape(end) + r"\n?", re.DOTALL)
    return pattern.sub("\n", text).rstrip() + "\n"


def _wiki_link(ctx: WorkstationContext, path: Path, label: str | None = None) -> str:
    rel = relative_to_target(ctx, path)
    return f"[[{rel}|{label or path.stem}]]"


def collect_codex_tasks(ctx: WorkstationContext, note_date: str) -> list[dict[str, str]]:
    tasks = []
    for path in markdown_files(configured_path(ctx, "codex_tasks_dir")):
        front = read_frontmatter(path)
        if str(front.get("date", "")) != note_date:
            continue
        tasks.append(
            {
                "task": str(front.get("task", path.stem)),
                "project": str(front.get("project", "unknown")),
                "status": str(front.get("status", "unknown")),
                "verified": str(front.get("verified", False)).lower(),
                "risk": str(front.get("risk", "unknown")),
                "link": _wiki_link(ctx, path, str(front.get("task", path.stem))),
            }
        )
    return sorted(tasks, key=lambda item: item["task"])


def collect_reviews(ctx: WorkstationContext, note_date: str) -> list[dict[str, str]]:
    reviews = []
    for path in markdown_files(configured_path(ctx, "reviews_dir")):
        front = read_frontmatter(path)
        period = str(front.get("period", ""))
        if period != note_date and not period.startswith(note_date[:4]):
            continue
        reviews.append(
            {
                "period": period,
                "review_type": str(front.get("review_type", "unknown")),
                "status": str(front.get("status", "unknown")),
                "link": _wiki_link(ctx, path, path.stem),
            }
        )
    return reviews[:8]


def collect_learning_notes(ctx: WorkstationContext, note_date: str) -> list[dict[str, str]]:
    notes = []
    learning_root = ctx.target_root / "06_Learning"
    for path in markdown_files(learning_root):
        front = read_frontmatter(path)
        if str(front.get("date", "")) != note_date:
            continue
        topic = str(front.get("topic", path.stem))
        notes.append(
            {
                "topic": topic,
                "area": str(front.get("area", path.parent.name)),
                "project": str(front.get("project", "none")),
                "status": str(front.get("novelty") or front.get("status", "unknown")),
                "link": _wiki_link(ctx, path, topic),
            }
        )
    return sorted(notes, key=lambda item: (item["area"], item["topic"]))


def collect_document_logs(ctx: WorkstationContext, note_date: str) -> list[dict[str, str]]:
    notes = []
    document_root = ctx.target_root / "08_Artifacts" / "Document_Logs"
    for path in markdown_files(document_root):
        front = read_frontmatter(path)
        if str(front.get("date", "")) != note_date:
            continue
        title = str(front.get("title", path.stem))
        notes.append(
            {
                "title": title,
                "project": str(front.get("project", "none")),
                "status": str(front.get("status", "unknown")),
                "artifact_path": str(front.get("artifact_path", "none")),
                "link": _wiki_link(ctx, path, title),
            }
        )
    return sorted(notes, key=lambda item: item["title"])


def collect_project_logs(ctx: WorkstationContext, note_date: str) -> list[dict[str, str]]:
    notes = []
    for path in markdown_files(configured_path(ctx, "projects_dir")):
        front = read_frontmatter(path)
        if str(front.get("type", "")) != "project-log" or str(front.get("date", "")) != note_date:
            continue
        title = str(front.get("title", path.stem))
        notes.append(
            {
                "title": title,
                "project": str(front.get("project", path.parent.parent.name if path.parent.name == "Logs" else "unknown")),
                "category": str(front.get("category", "progress")),
                "status": str(front.get("status", "unknown")),
                "link": _wiki_link(ctx, path, title),
            }
        )
    return sorted(notes, key=lambda item: (item["project"], item["title"]))


def collect_recent_inbox_entries(ctx: WorkstationContext, note_date: str) -> list[str]:
    inbox = ctx.target_root / "00_Inbox" / "Inbox.md"
    if not inbox.exists():
        return []
    text = inbox.read_text(encoding="utf-8", errors="ignore")
    entries = []
    pattern = re.compile(r"^##\s+([0-9T:+\-]+)\s+-\s+(.+)$", re.MULTILINE)
    for match in pattern.finditer(text):
        timestamp, title = match.groups()
        if timestamp.startswith(note_date):
            entries.append(f"- {timestamp} - {title}")
    return entries[-8:]


def collect_pending_review(ctx: WorkstationContext) -> list[dict[str, str]]:
    pending = []
    for path in markdown_files(ctx.target_root):
        front = read_frontmatter(path)
        if front.get("human_review_required") is True or front.get("human_reviewed") is False:
            title = str(front.get("task") or front.get("topic") or front.get("project") or path.stem)
            pending.append(
                {
                    "type": str(front.get("type", "markdown")),
                    "title": title,
                    "link": _wiki_link(ctx, path, title),
                }
            )
    return pending[:12]


def render_daily_sync(ctx: WorkstationContext, note_date: str) -> str:
    tasks = collect_codex_tasks(ctx, note_date)
    learning_notes = collect_learning_notes(ctx, note_date)
    document_logs = collect_document_logs(ctx, note_date)
    project_logs = collect_project_logs(ctx, note_date)
    reviews = collect_reviews(ctx, note_date)
    inbox_entries = collect_recent_inbox_entries(ctx, note_date)
    pending = collect_pending_review(ctx)

    task_lines = [
        f"- {item['link']} · project={item['project']} · status={item['status']} · verified={item['verified']} · risk={item['risk']}"
        for item in tasks
    ] or ["- 暂无当天 Codex 任务。"]
    learning_lines = [
        f"- {item['link']} · area={item['area']} · project={item['project']} · status={item['status']}"
        for item in learning_notes
    ] or ["- 暂无当天学习记录。"]
    document_lines = [
        f"- {item['link']} · project={item['project']} · status={item['status']} · artifact={item['artifact_path']}"
        for item in document_logs
    ] or ["- 暂无当天文档写作记录。"]
    project_log_lines = [
        f"- {item['link']} · project={item['project']} · category={item['category']} · status={item['status']}"
        for item in project_logs
    ] or ["- 暂无当天项目细节日志。"]
    review_lines = [
        f"- {item['link']} · type={item['review_type']} · period={item['period']} · status={item['status']}"
        for item in reviews
    ] or ["- 暂无关联复盘。"]
    inbox_lines = inbox_entries or ["- 暂无当天 Inbox 新增条目。"]
    pending_lines = [f"- {item['link']} · type={item['type']}" for item in pending] or ["- 暂无待审核内容。"]

    return f"""## 自动汇总

### Codex 任务
{chr(10).join(task_lines)}

### 学习记录
{chr(10).join(learning_lines)}

### 文档写作
{chr(10).join(document_lines)}

### 项目细节
{chr(10).join(project_log_lines)}

### Inbox 新增
{chr(10).join(inbox_lines)}

### 关联复盘
{chr(10).join(review_lines)}

### 待审核队列
{chr(10).join(pending_lines)}

### 汇总边界
- generated_by: personal_workstation.sync_daily
- preview: {str(ctx.config.get("preview_mode", True)).lower()}
- human_review_required: true
"""


def sync_daily(ctx: WorkstationContext, note_date: str | None = None):
    note_date = note_date or today_string(ctx)
    daily_path = configured_path(ctx, "daily_dir") / f"{note_date}.md"
    if not daily_path.exists():
        create_daily_note(ctx, note_date)
    text = daily_path.read_text(encoding="utf-8", errors="ignore")
    cleaned = remove_marked_section(text, DAILY_SYNC_MARKER)
    if cleaned != text:
        write_text_file(daily_path, cleaned, overwrite=True)

    sync_path = configured_path(ctx, "system_dir") / "Daily_Sync" / f"{note_date}.md"
    return write_text_file(sync_path, render_daily_sync(ctx, note_date), overwrite=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync generated workstation summaries into a daily note.")
    parser.add_argument("--config", default=None)
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    ctx = make_context(args.config)
    result = sync_daily(ctx, args.date)
    print(f"{result.action}: {result.path}")


if __name__ == "__main__":
    main()
