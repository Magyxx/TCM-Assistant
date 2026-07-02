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


def learning_note_content(
    ctx: WorkstationContext,
    note_date: str,
    area: str,
    topic: str,
    summary: str,
    material_source: str,
    project_name: str,
) -> str:
    return frontmatter(
        {
            "type": "learning-note",
            "id": stable_id("learning-note", f"{note_date}-{area}-{topic}"),
            "date": note_date,
            "area": area,
            "topic": topic,
            "project": project_name or "none",
            "status": "captured",
            "material_source": material_source or "manual",
            "source": "personal_workstation.write_learning_note",
            "preview": bool(ctx.config.get("preview_mode", True)),
            "human_review_required": True,
            "human_reviewed": False,
            "created": note_date,
            "updated": note_date,
        },
        ["learning", "workstation"],
    ) + f"""# {topic}

## 学习目标
- {summary or "补充本次学习想解决的问题。"}

## 输入材料
- source: {material_source or "manual"}

## 关键概念
- 待补充。

## 实践/练习
- 待补充。

## 项目关联
- project: {project_name or "none"}
- 本次学习如何影响项目实现：待补充。

## 疑问
- 待补充。

## 可沉淀知识卡片
- [ ] 是否需要整理到 `04_Knowledge/`。

## 今日结论
- 待人工复核后补充。

## 下一步
- [ ] 明确下一次学习或实践动作。

## 审核状态
- human_reviewed: false
- human_review_required: true
"""


def create_learning_note(
    ctx: WorkstationContext,
    note_date: str | None = None,
    area: str = "Agent",
    topic: str = "学习记录",
    summary: str = "",
    material_source: str = "manual",
    project_name: str = "",
):
    note_date = note_date or today_string(ctx)
    learning_dir = ctx.target_root / "06_Learning" / safe_slug(area, "General")
    path = learning_dir / f"{note_date}_{safe_slug(topic)}.md"
    return write_text_file(
        path,
        learning_note_content(ctx, note_date, area, topic, summary, material_source, project_name),
        overwrite=bool(ctx.config.get("allow_overwrite", False)),
        unique_on_conflict=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a learning note for the Personal AI Workstation.")
    parser.add_argument("--config", default=None)
    parser.add_argument("--date", default=None)
    parser.add_argument("--area", default="Agent")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--summary", default="")
    parser.add_argument("--material-source", default="manual")
    parser.add_argument("--project", default="")
    args = parser.parse_args()
    ctx = make_context(args.config)
    result = create_learning_note(
        ctx,
        args.date,
        args.area,
        args.topic,
        args.summary,
        args.material_source,
        args.project,
    )
    print(f"{result.action}: {result.path}")


if __name__ == "__main__":
    main()
