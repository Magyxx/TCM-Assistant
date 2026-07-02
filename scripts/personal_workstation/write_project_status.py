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


PROJECT_FILES = {
    "Overview.md": "项目总览",
    "Current_Status.md": "当前状态",
    "Roadmap.md": "路线图",
    "Version_Index.md": "版本索引",
    "Task_Pool.md": "任务池",
    "Decision_Log.md": "决策记录",
    "Risk_Log.md": "风险记录",
    "Codex_Task_Log.md": "Codex 任务记录",
    "Artifact_Index.md": "产物索引",
}


def project_frontmatter(
    project_name: str,
    project_type: str = "general",
    area: str = "workstation",
    note_date: str | None = None,
) -> str:
    return frontmatter(
        {
            "type": "project",
            "project_id": stable_id("project", project_name),
            "project": project_name,
            "project_type": project_type,
            "area": area,
            "status": "active",
            "priority": "medium",
            "stage": "unknown",
            "source": "personal_workstation.write_project_status",
            "human_review_required": True,
            "human_reviewed": False,
            "created": note_date or "unknown",
            "updated": note_date or "unknown",
        },
        ["project"],
    )


def project_file_content(
    file_name: str,
    project_name: str,
    note_date: str,
    project_type: str = "general",
    area: str = "workstation",
    description: str = "",
    goal: str = "",
) -> str:
    title = PROJECT_FILES[file_name]
    if file_name == "Overview.md":
        body = f"""## 项目定位
{description or "这是一个可长期维护的项目模块，不绑定具体业务形态。"}

## 项目类型
- {project_type}
- {area}

## 长期目标
{goal or "待补充。"}

## 项目边界
- 本项目作为个人 AI 工作站的 `02_Projects/` 模块接入。
- 任务记录、产物、风险和复盘必须能追溯来源。
- 重要结论默认需要人工审核。
"""
    elif file_name == "Current_Status.md":
        body = f"""## 当前状态
- status: active
- updated: {note_date}
- stage: unknown
- progress: 0%

## 阶段目标
- [ ] {goal or "补充项目阶段目标。"}

## 当前风险
- 项目描述、目标、边界仍需人工确认。
- 自动生成状态不能替代真实项目复盘。
"""
    elif file_name == "Roadmap.md":
        body = """## Phase 1 - MVP
- 本地 preview 工作站
- Markdown / JSON / Canvas / HTML 静态产物
- 验证脚本

## Phase 2 - Obsidian 接入
- 配置真实 vault path
- 增量写入真实项目记录
- Dataview / Bases 查询视图

## Phase 3 - Local AI
- 本地 embedding
- 本地 RAG
- 多 Agent 工作流
"""
    elif file_name == "Version_Index.md":
        body = f"""| Version | Date | Scope | Evidence | Review |
| --- | --- | --- | --- | --- |
| v0.1 | {note_date} | 项目接入初始化 | 当前项目骨架 | required |
"""
    elif file_name == "Task_Pool.md":
        body = """## Backlog
- [ ] 补充项目真实阶段目标。
- [ ] 补充最近三条可执行任务。
- [ ] 标记任务优先级和截止时间。

## Doing
- [ ] 待补充。

## Done
- [ ] 初始化项目模块。
"""
    elif file_name == "Decision_Log.md":
        body = f"""| Date | Decision | Reason | Review |
| --- | --- | --- | --- |
| {note_date} | 默认 preview mode | 避免误写真实 Obsidian vault | required |
| {note_date} | Markdown + JSON 双轨输出 | 兼顾 Obsidian 回看与 Dashboard 可视化 | required |
"""
    elif file_name == "Risk_Log.md":
        body = f"""| Date | Risk | Level | Mitigation | Status |
| --- | --- | --- | --- | --- |
| {note_date} | 自动生成内容被误认为已人工确认 | medium | frontmatter 标注 human_review_required | open |
| {note_date} | 写入真实 vault 时覆盖已有笔记 | high | 默认 allow_overwrite=false | controlled |
"""
    elif file_name == "Codex_Task_Log.md":
        body = """## Codex 任务索引
- 待关联 `03_Codex_Tasks/` 下的任务记录。

| Date | Task | Result | Verification |
| --- | --- | --- | --- |
| 待补充 | 待补充 | 待补充 | 待补充 |
"""
    else:
        body = """## 产物索引
- `00_Home/AI_Workstation.canvas`
- `workstation_state.json`
- `dashboard.html`
- `01_Daily/`
- `03_Codex_Tasks/`
- `04_Knowledge/`
"""
    return project_frontmatter(project_name, project_type, area, note_date) + f"# {project_name} - {title}\n\n{body}"


def create_project_status(
    ctx: WorkstationContext,
    project_name: str = "Personal AI Workstation",
    note_date: str | None = None,
    project_type: str = "general",
    area: str = "workstation",
    description: str = "",
    goal: str = "",
):
    note_date = note_date or today_string(ctx)
    project_dir = configured_path(ctx, "projects_dir") / safe_slug(project_name)
    (project_dir / "Logs").mkdir(parents=True, exist_ok=True)
    results = []
    for file_name in PROJECT_FILES:
        path = project_dir / file_name
        results.append(
            write_text_file(
                path,
                project_file_content(file_name, project_name, note_date, project_type, area, description, goal),
                overwrite=bool(ctx.config.get("allow_overwrite", False)),
            )
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or seed project status notes.")
    parser.add_argument("--config", default=None)
    parser.add_argument("--project", default="Personal AI Workstation")
    parser.add_argument("--date", default=None)
    parser.add_argument("--project-type", default="general")
    parser.add_argument("--area", default="workstation")
    parser.add_argument("--description", default="")
    parser.add_argument("--goal", default="")
    args = parser.parse_args()
    ctx = make_context(args.config)
    for result in create_project_status(
        ctx,
        args.project,
        args.date,
        args.project_type,
        args.area,
        args.description,
        args.goal,
    ):
        print(f"{result.action}: {result.path}")


if __name__ == "__main__":
    main()
