from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.personal_workstation.common import (  # noqa: E402
    WorkstationContext,
    configured_path,
    frontmatter,
    make_context,
    safe_slug,
    stable_id,
    today_string,
    write_text_file,
)


def project_log_content(
    ctx: WorkstationContext,
    note_date: str,
    project_name: str,
    title: str,
    category: str,
    summary: str,
    decision: str,
    next_step: str,
) -> str:
    return frontmatter(
        {
            "type": "project-log",
            "id": stable_id("project-log", f"{note_date}-{project_name}-{title}"),
            "date": note_date,
            "project": project_name,
            "project_id": stable_id("project", project_name),
            "title": title,
            "category": category,
            "status": "captured",
            "source": "personal_workstation.write_project_log",
            "preview": bool(ctx.config.get("preview_mode", True)),
            "human_review_required": True,
            "human_reviewed": False,
            "created": note_date,
            "updated": note_date,
        },
        ["project-log", "workstation"],
    ) + f"""# {title}

## 项目
- project: {project_name}
- category: {category}
- date: {note_date}

## 发生了什么
{summary or "补充本次项目细节。"}

## 关键决策
{decision or "- 待补充。"}

## 证据/上下文
- 待补充相关文件、链接、截图或命令输出。

## 影响范围
- 待补充对功能、架构、排期、风险或文档的影响。

## 下一步
- [ ] {next_step or "补充下一步动作。"}

## 审核状态
- human_reviewed: false
- human_review_required: true
"""


def create_project_log(
    ctx: WorkstationContext,
    note_date: str | None = None,
    project_name: str = "Personal AI Workstation",
    title: str = "项目日志",
    category: str = "progress",
    summary: str = "",
    decision: str = "",
    next_step: str = "",
):
    note_date = note_date or today_string(ctx)
    project_dir = configured_path(ctx, "projects_dir") / safe_slug(project_name) / "Logs"
    path = project_dir / f"{note_date}_{safe_slug(title)}.md"
    return write_text_file(
        path,
        project_log_content(ctx, note_date, project_name, title, category, summary, decision, next_step),
        overwrite=bool(ctx.config.get("allow_overwrite", False)),
        unique_on_conflict=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a project detail log.")
    parser.add_argument("--config", default=None)
    parser.add_argument("--date", default=None)
    parser.add_argument("--project", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--category", default="progress")
    parser.add_argument("--summary", default="")
    parser.add_argument("--decision", default="")
    parser.add_argument("--next-step", default="")
    args = parser.parse_args()
    ctx = make_context(args.config)
    result = create_project_log(
        ctx,
        args.date,
        args.project,
        args.title,
        args.category,
        args.summary,
        args.decision,
        args.next_step,
    )
    print(f"{result.action}: {result.path}")


if __name__ == "__main__":
    main()
