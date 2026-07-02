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


def codex_task_content(
    ctx: WorkstationContext,
    note_date: str,
    project_name: str,
    task_title: str,
    summary: str,
) -> str:
    preview = bool(ctx.config.get("preview_mode", True))
    return frontmatter(
        {
            "type": "codex-task",
            "id": stable_id("codex-task", f"{note_date}-{project_name}-{task_title}"),
            "date": note_date,
            "project": project_name,
            "project_id": stable_id("project", project_name),
            "task": task_title,
            "status": "completed",
            "verified": False,
            "real_execution": "unknown",
            "real_provider_called": "unknown",
            "network_used": False,
            "model_weights_trained": False,
            "mock": "unknown",
            "preview": preview,
            "dry_run": "unknown",
            "human_review_required": True,
            "human_reviewed": False,
            "risk": "medium",
            "source": "personal_workstation.write_codex_task_note",
            "created": note_date,
            "updated": note_date,
        },
        ["codex", "task-log"],
    ) + f"""# {task_title}

## 任务目标
{summary}

## 输入材料
- 用户请求或本地项目上下文。

## 实际完成内容
- 待由 Codex 在任务结束时补充精确变更。

## Changed Files
- 待补充。

## Generated Artifacts
- 待补充。

## 验证结果
- verified: false
- 当前记录默认需要人工复核。

## 执行边界
- real_execution: unknown
- network_used: false
- real_provider_called: unknown
- model_weights_trained: false
- mock: unknown
- preview: {str(preview).lower()}
- dry_run: unknown

## 未完成内容
- 待补充。

## 风险与幻觉检查
- 任何项目判断、知识结论、外部事实都需要人工确认。

## 下一步建议
- 任务完成后补全 Changed Files、验证结果与风险边界。
"""


def create_codex_task_note(
    ctx: WorkstationContext,
    note_date: str | None = None,
    project_name: str = "Personal AI Workstation",
    task_title: str = "Bootstrap MVP",
    summary: str = "生成个人 AI 工作站第一阶段 MVP 骨架。",
):
    note_date = note_date or today_string(ctx)
    filename = f"{note_date}_{safe_slug(project_name)}_{safe_slug(task_title)}.md"
    path = configured_path(ctx, "codex_tasks_dir") / filename
    return write_text_file(
        path,
        codex_task_content(ctx, note_date, project_name, task_title, summary),
        overwrite=bool(ctx.config.get("allow_overwrite", False)),
        unique_on_conflict=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a Codex task note.")
    parser.add_argument("--config", default=None)
    parser.add_argument("--date", default=None)
    parser.add_argument("--project", default="Personal AI Workstation")
    parser.add_argument("--task", default="Bootstrap MVP")
    parser.add_argument("--summary", default="生成个人 AI 工作站第一阶段 MVP 骨架。")
    args = parser.parse_args()
    ctx = make_context(args.config)
    result = create_codex_task_note(ctx, args.date, args.project, args.task, args.summary)
    print(f"{result.action}: {result.path}")


if __name__ == "__main__":
    main()
