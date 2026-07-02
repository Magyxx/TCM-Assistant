from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.personal_workstation.common import (  # noqa: E402
    WorkstationContext,
    frontmatter,
    make_context,
    safe_slug,
    stable_id,
    today_string,
    write_text_file,
)


def document_note_content(
    ctx: WorkstationContext,
    note_date: str,
    title: str,
    project_name: str,
    artifact_path: str,
    audience: str,
    summary: str,
    status: str,
) -> str:
    return frontmatter(
        {
            "type": "document-log",
            "id": stable_id("document-log", f"{note_date}-{title}"),
            "date": note_date,
            "title": title,
            "project": project_name or "none",
            "artifact_path": artifact_path or "none",
            "audience": audience or "self",
            "status": status,
            "source": "personal_workstation.write_document_note",
            "preview": bool(ctx.config.get("preview_mode", True)),
            "human_review_required": True,
            "human_reviewed": False,
            "created": note_date,
            "updated": note_date,
        },
        ["document", "artifact", "workstation"],
    ) + f"""# {title}

## 文档目标
{summary or "补充这份文档要解决的问题。"}

## 目标读者
- {audience or "self"}

## 结构大纲
- 背景
- 关键内容
- 结论
- 后续动作

## 已完成内容
- 待补充。

## 关联项目
- project: {project_name or "none"}

## 关联产物
- artifact_path: `{artifact_path or "none"}`

## 待完善
- [ ] 补齐正文。
- [ ] 检查事实、结论和引用。
- [ ] 决定是否沉淀为知识卡片或项目日志。

## 审核状态
- status: {status}
- human_reviewed: false
- human_review_required: true
"""


def create_document_note(
    ctx: WorkstationContext,
    note_date: str | None = None,
    title: str = "文档记录",
    project_name: str = "",
    artifact_path: str = "",
    audience: str = "self",
    summary: str = "",
    status: str = "draft",
):
    note_date = note_date or today_string(ctx)
    document_dir = ctx.target_root / "08_Artifacts" / "Document_Logs"
    path = document_dir / f"{note_date}_{safe_slug(title)}.md"
    return write_text_file(
        path,
        document_note_content(ctx, note_date, title, project_name, artifact_path, audience, summary, status),
        overwrite=bool(ctx.config.get("allow_overwrite", False)),
        unique_on_conflict=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a document-writing log.")
    parser.add_argument("--config", default=None)
    parser.add_argument("--date", default=None)
    parser.add_argument("--title", required=True)
    parser.add_argument("--project", default="")
    parser.add_argument("--artifact-path", default="")
    parser.add_argument("--audience", default="self")
    parser.add_argument("--summary", default="")
    parser.add_argument("--status", default="draft")
    args = parser.parse_args()
    ctx = make_context(args.config)
    result = create_document_note(
        ctx,
        args.date,
        args.title,
        args.project,
        args.artifact_path,
        args.audience,
        args.summary,
        args.status,
    )
    print(f"{result.action}: {result.path}")


if __name__ == "__main__":
    main()
