from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.personal_workstation.common import (  # noqa: E402
    WorkstationContext,
    append_text_file,
    frontmatter,
    make_context,
    now,
    write_text_file,
)


def ensure_inbox(ctx: WorkstationContext):
    path = ctx.target_root / "00_Inbox" / "Inbox.md"
    if path.exists():
        return None
    content = frontmatter(
        {
            "type": "inbox",
            "status": "active",
            "source": "personal_workstation.write_inbox_entry",
            "human_review_required": True,
        },
        ["inbox", "workstation"],
    ) + "# Inbox\n\n"
    return write_text_file(path, content, overwrite=False)


def append_inbox_entry(
    ctx: WorkstationContext,
    title: str,
    body: str,
    category: str = "thought",
    source: str = "manual",
    entry_date: str | None = None,
):
    ensure_inbox(ctx)
    timestamp = f"{entry_date}T00:00:00" if entry_date else now(ctx).isoformat(timespec="seconds")
    path = ctx.target_root / "00_Inbox" / "Inbox.md"
    entry = f"""
## {timestamp} - {title}

- category: {category}
- source: {source}
- status: pending-review
- preview: {str(ctx.config.get("preview_mode", True)).lower()}

{body.strip()}
"""
    return append_text_file(path, entry)


def main() -> None:
    parser = argparse.ArgumentParser(description="Append an item to the workstation inbox.")
    parser.add_argument("--config", default=None)
    parser.add_argument("--title", required=True)
    parser.add_argument("--body", required=True)
    parser.add_argument("--category", default="thought")
    parser.add_argument("--source", default="manual")
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    ctx = make_context(args.config)
    result = append_inbox_entry(ctx, args.title, args.body, args.category, args.source, args.date)
    print(f"{result.action}: {result.path}")


if __name__ == "__main__":
    main()
