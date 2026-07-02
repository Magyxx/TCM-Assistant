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
    stable_id,
    today_string,
    write_text_file,
)


def daily_note_content(ctx: WorkstationContext, note_date: str) -> str:
    return frontmatter(
        {
            "type": "daily",
            "id": stable_id("daily", note_date),
            "date": note_date,
            "status": "active",
            "source": "personal_workstation.write_daily_note",
            "created": note_date,
            "updated": note_date,
        },
        ["daily", "workstation"],
    ) + f"""# {note_date} Daily Workflow

## 今日目标
- [ ] 明确今天最重要的 1-3 个目标。

## 今日执行记录
- 待补充。

## 今日复盘
- 做得好的：
- 需要改进：
- 关键判断：

## 明日下一步
- [ ] 待补充。
"""


def create_daily_note(ctx: WorkstationContext, note_date: str | None = None):
    note_date = note_date or today_string(ctx)
    path = configured_path(ctx, "daily_dir") / f"{note_date}.md"
    return write_text_file(
        path,
        daily_note_content(ctx, note_date),
        overwrite=bool(ctx.config.get("allow_overwrite", False)),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a daily note for the Personal AI Workstation.")
    parser.add_argument("--config", default=None)
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    ctx = make_context(args.config)
    result = create_daily_note(ctx, args.date)
    print(f"{result.action}: {result.path}")


if __name__ == "__main__":
    main()
