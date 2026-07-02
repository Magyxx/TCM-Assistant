from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.personal_workstation.build_canvas import build_canvas  # noqa: E402
from scripts.personal_workstation.build_dashboard_state import build_dashboard_state  # noqa: E402
from scripts.personal_workstation.build_indexes import build_indexes  # noqa: E402
from scripts.personal_workstation.build_obsidian_views import build_obsidian_views  # noqa: E402
from scripts.personal_workstation.build_rag_manifest import build_rag_manifest  # noqa: E402
from scripts.personal_workstation.build_search_index import build_search_index  # noqa: E402
from scripts.personal_workstation.build_static_dashboard import build_static_dashboard  # noqa: E402
from scripts.personal_workstation.common import WorkstationContext, today_string  # noqa: E402
from scripts.personal_workstation.normalize_metadata import normalize_metadata  # noqa: E402
from scripts.personal_workstation.sync_daily import sync_daily  # noqa: E402
from scripts.personal_workstation.write_daily_note import create_daily_note  # noqa: E402
from scripts.personal_workstation.write_review_note import create_review_note  # noqa: E402
from scripts.personal_workstation.common import make_context  # noqa: E402


def daily_closeout(ctx: WorkstationContext, note_date: str | None = None):
    note_date = note_date or today_string(ctx)
    results = []
    results.append(create_daily_note(ctx, note_date))
    results.append(create_review_note(ctx, "daily", note_date))
    results.append(sync_daily(ctx, note_date))
    results.extend(normalize_metadata(ctx))
    results.append(build_canvas(ctx))
    results.extend(build_indexes(ctx))
    results.extend(build_obsidian_views(ctx))
    results.extend(build_rag_manifest(ctx))
    results.extend(build_search_index(ctx))
    state_result, state = build_dashboard_state(ctx, note_date)
    results.append(state_result)
    results.append(build_static_dashboard(ctx, state, note_date))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run daily closeout for the Personal AI Workstation.")
    parser.add_argument("--config", default=None)
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    ctx = make_context(args.config)
    for result in daily_closeout(ctx, args.date):
        print(f"{result.action}: {result.path}")


if __name__ == "__main__":
    main()
