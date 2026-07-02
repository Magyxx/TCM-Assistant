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
    now,
    safe_slug,
    stable_id,
    today_string,
    write_text_file,
)


def period_key(ctx: WorkstationContext, review_type: str, explicit_date: str | None = None) -> str:
    if explicit_date:
        date_text = explicit_date
    else:
        date_text = today_string(ctx)
    if review_type == "daily":
        return date_text
    current = now(ctx).date()
    if explicit_date:
        from datetime import date

        year, month, day = [int(part) for part in explicit_date.split("-")]
        current = date(year, month, day)
    if review_type == "weekly":
        iso = current.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    if review_type == "monthly":
        return date_text[:7]
    return date_text


def review_path(
    ctx: WorkstationContext,
    review_type: str,
    date_text: str | None = None,
    project: str | None = None,
    phase: str | None = None,
) -> Path:
    reviews_root = ctx.target_root / str(ctx.config["reviews_dir"])
    if review_type == "daily":
        return reviews_root / "Daily" / f"{period_key(ctx, review_type, date_text)}.md"
    if review_type == "weekly":
        return reviews_root / "Weekly" / f"{period_key(ctx, review_type, date_text)}.md"
    if review_type == "monthly":
        return reviews_root / "Monthly" / f"{period_key(ctx, review_type, date_text)}.md"
    project_name = safe_slug(project or "Personal AI Workstation")
    phase_name = safe_slug(phase or "phase")
    return reviews_root / "Project_Reviews" / f"{project_name}_{phase_name}.md"


def review_content(
    ctx: WorkstationContext,
    review_type: str,
    date_text: str | None = None,
    project: str | None = None,
    phase: str | None = None,
) -> str:
    key = period_key(ctx, review_type, date_text)
    fields = {
        "type": "review",
        "id": stable_id("review", f"{review_type}-{key}-{project or ''}-{phase or ''}"),
        "review_type": review_type,
        "period": key,
        "status": "draft",
        "source": "personal_workstation.write_review_note",
        "human_review_required": True,
        "human_reviewed": False,
        "preview": bool(ctx.config.get("preview_mode", True)),
        "created": date_text or today_string(ctx),
        "updated": date_text or today_string(ctx),
    }
    if project:
        fields["project"] = project
    if phase:
        fields["phase"] = phase
    title = f"{review_type.title()} Review - {key}"
    if review_type == "project":
        title = f"Project Review - {project or 'Personal AI Workstation'} - {phase or 'phase'}"
    return frontmatter(fields, ["review", "workstation"]) + f"""# {title}

## 本周期目标
- 待补充。

## 已完成
- 待补充。

## 关键证据
- 关联 Daily Note：
- 关联 Codex Task：
- 关联项目状态：
- 关联产物：

## 问题与风险
- 待补充。

## 知识沉淀
- 待转化为知识卡片：

## 决策记录
- 待补充。

## 下一周期行动
- [ ] 待补充。

## 人工审核
- human_review_required: true
- human_reviewed: false
"""


def create_review_note(
    ctx: WorkstationContext,
    review_type: str,
    date_text: str | None = None,
    project: str | None = None,
    phase: str | None = None,
):
    path = review_path(ctx, review_type, date_text, project, phase)
    return write_text_file(
        path,
        review_content(ctx, review_type, date_text, project, phase),
        overwrite=bool(ctx.config.get("allow_overwrite", False)),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a review note.")
    parser.add_argument("--config", default=None)
    parser.add_argument("--type", choices=["daily", "weekly", "monthly", "project"], default="weekly")
    parser.add_argument("--date", default=None)
    parser.add_argument("--project", default=None)
    parser.add_argument("--phase", default=None)
    args = parser.parse_args()
    ctx = make_context(args.config)
    result = create_review_note(ctx, args.type, args.date, args.project, args.phase)
    print(f"{result.action}: {result.path}")


if __name__ == "__main__":
    main()
