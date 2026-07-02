from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.personal_workstation.build_dashboard_state import build_dashboard_state  # noqa: E402
from scripts.personal_workstation.build_indexes import build_indexes  # noqa: E402
from scripts.personal_workstation.build_static_dashboard import build_static_dashboard  # noqa: E402
from scripts.personal_workstation.common import WorkstationContext, make_context, today_string  # noqa: E402
from scripts.personal_workstation.write_inbox_entry import append_inbox_entry  # noqa: E402
from scripts.personal_workstation.write_project_status import create_project_status  # noqa: E402


def onboard_project(
    ctx: WorkstationContext,
    name: str,
    project_type: str = "general",
    area: str = "workstation",
    description: str = "",
    goal: str = "",
    note_date: str | None = None,
):
    note_date = note_date or today_string(ctx)
    results = []
    results.extend(create_project_status(ctx, name, note_date, project_type, area, description, goal))
    results.append(
        append_inbox_entry(
            ctx,
            f"审核新接入项目：{name}",
            f"项目类型：{project_type}\n领域：{area}\n长期目标：{goal or '待补充'}\n请人工确认项目边界、阶段目标、风险和产物路径。",
            category="project-onboarding",
            source="personal_workstation.onboard_project",
            entry_date=note_date,
        )
    )
    results.extend(build_indexes(ctx))
    state_result, state = build_dashboard_state(ctx, note_date)
    results.append(state_result)
    results.append(build_static_dashboard(ctx, state, note_date))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Onboard an existing project into the Personal AI Workstation.")
    parser.add_argument("--config", default=None)
    parser.add_argument("--name", required=True)
    parser.add_argument("--project-type", default="general")
    parser.add_argument("--area", default="workstation")
    parser.add_argument("--description", default="")
    parser.add_argument("--goal", default="")
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    ctx = make_context(args.config)
    for result in onboard_project(
        ctx,
        args.name,
        args.project_type,
        args.area,
        args.description,
        args.goal,
        args.date,
    ):
        print(f"{result.action}: {result.path}")


if __name__ == "__main__":
    main()
