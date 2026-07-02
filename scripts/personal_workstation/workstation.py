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
from scripts.personal_workstation.common import WriteResult, make_context  # noqa: E402
from scripts.personal_workstation.daily_closeout import daily_closeout  # noqa: E402
from scripts.personal_workstation.init_workstation import initialize_workstation  # noqa: E402
from scripts.personal_workstation.normalize_metadata import normalize_metadata  # noqa: E402
from scripts.personal_workstation.onboard_project import onboard_project  # noqa: E402
from scripts.personal_workstation.plan_automation import adjust_plan  # noqa: E402
from scripts.personal_workstation.sync_daily import sync_daily  # noqa: E402
from scripts.personal_workstation.verify_workstation import run_checks  # noqa: E402
from scripts.personal_workstation.write_agent_research_note import create_agent_research_note  # noqa: E402
from scripts.personal_workstation.write_codex_task_note import create_codex_task_note  # noqa: E402
from scripts.personal_workstation.write_daily_note import create_daily_note  # noqa: E402
from scripts.personal_workstation.write_inbox_entry import append_inbox_entry  # noqa: E402
from scripts.personal_workstation.write_document_note import create_document_note  # noqa: E402
from scripts.personal_workstation.write_knowledge_card import create_knowledge_card  # noqa: E402
from scripts.personal_workstation.write_learning_note import create_learning_note  # noqa: E402
from scripts.personal_workstation.write_project_log import create_project_log  # noqa: E402
from scripts.personal_workstation.write_project_status import create_project_status  # noqa: E402
from scripts.personal_workstation.write_review_note import create_review_note  # noqa: E402


def print_results(results: WriteResult | list[WriteResult]) -> None:
    if isinstance(results, WriteResult):
        results = [results]
    for result in results:
        print(f"{result.action}: {result.path}")


def rebuild(ctx, note_date: str | None = None) -> list[WriteResult]:
    results: list[WriteResult] = []
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
    parser = argparse.ArgumentParser(description="Unified CLI for the Personal AI Workstation.")
    parser.add_argument("--config", default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_cmd = subparsers.add_parser("init", help="Initialize preview or configured vault.")
    init_cmd.add_argument("--date", default=None)
    init_cmd.add_argument("--project", default="Personal AI Workstation")
    init_cmd.add_argument("--task", default="Bootstrap MVP")
    init_cmd.add_argument("--topic", default="个人 AI 工作站的本地优先知识沉淀")

    daily_cmd = subparsers.add_parser("daily", help="Create a daily note.")
    daily_cmd.add_argument("--date", default=None)

    project_cmd = subparsers.add_parser("project", help="Create or seed project notes.")
    project_cmd.add_argument("--name", required=True)
    project_cmd.add_argument("--date", default=None)
    project_cmd.add_argument("--project-type", default="general")
    project_cmd.add_argument("--area", default="workstation")
    project_cmd.add_argument("--description", default="")
    project_cmd.add_argument("--goal", default="")

    onboard_cmd = subparsers.add_parser("onboard-project", help="Onboard an existing project and refresh indexes.")
    onboard_cmd.add_argument("--name", required=True)
    onboard_cmd.add_argument("--project-type", default="general")
    onboard_cmd.add_argument("--area", default="workstation")
    onboard_cmd.add_argument("--description", default="")
    onboard_cmd.add_argument("--goal", default="")
    onboard_cmd.add_argument("--date", default=None)

    task_cmd = subparsers.add_parser("codex-task", help="Create a Codex task note.")
    task_cmd.add_argument("--project", required=True)
    task_cmd.add_argument("--task", required=True)
    task_cmd.add_argument("--summary", default="待补充。")
    task_cmd.add_argument("--date", default=None)

    knowledge_cmd = subparsers.add_parser("knowledge", help="Create a knowledge card.")
    knowledge_cmd.add_argument("--topic", required=True)
    knowledge_cmd.add_argument("--domain", default="AI")

    learning_cmd = subparsers.add_parser("learning", help="Create a daily learning note.")
    learning_cmd.add_argument("--date", default=None)
    learning_cmd.add_argument("--area", default="Agent")
    learning_cmd.add_argument("--topic", required=True)
    learning_cmd.add_argument("--summary", default="")
    learning_cmd.add_argument("--material-source", default="manual")
    learning_cmd.add_argument("--project", default="")

    agent_research_cmd = subparsers.add_parser("agent-research", help="Create a daily Agent engineering research note.")
    agent_research_cmd.add_argument("--date", default=None)
    agent_research_cmd.add_argument("--input-json", default=None)

    document_cmd = subparsers.add_parser("document", help="Create a document-writing log.")
    document_cmd.add_argument("--date", default=None)
    document_cmd.add_argument("--title", required=True)
    document_cmd.add_argument("--project", default="")
    document_cmd.add_argument("--artifact-path", default="")
    document_cmd.add_argument("--audience", default="self")
    document_cmd.add_argument("--summary", default="")
    document_cmd.add_argument("--status", default="draft")

    project_log_cmd = subparsers.add_parser("project-log", help="Create a project detail log.")
    project_log_cmd.add_argument("--date", default=None)
    project_log_cmd.add_argument("--project", required=True)
    project_log_cmd.add_argument("--title", required=True)
    project_log_cmd.add_argument("--category", default="progress")
    project_log_cmd.add_argument("--summary", default="")
    project_log_cmd.add_argument("--decision", default="")
    project_log_cmd.add_argument("--next-step", default="")

    inbox_cmd = subparsers.add_parser("inbox", help="Append an inbox item.")
    inbox_cmd.add_argument("--title", required=True)
    inbox_cmd.add_argument("--body", required=True)
    inbox_cmd.add_argument("--category", default="thought")
    inbox_cmd.add_argument("--source", default="manual")
    inbox_cmd.add_argument("--date", default=None)

    review_cmd = subparsers.add_parser("review", help="Create a review note.")
    review_cmd.add_argument("--type", choices=["daily", "weekly", "monthly", "project"], default="weekly")
    review_cmd.add_argument("--date", default=None)
    review_cmd.add_argument("--project", default=None)
    review_cmd.add_argument("--phase", default=None)

    sync_cmd = subparsers.add_parser("sync-daily", help="Sync generated summaries into a daily note.")
    sync_cmd.add_argument("--date", default=None)

    rebuild_cmd = subparsers.add_parser("rebuild", help="Rebuild canvas, indexes, state, and dashboard.")
    rebuild_cmd.add_argument("--date", default=None)

    closeout_cmd = subparsers.add_parser("closeout", help="Run daily closeout: review, daily sync, views, dashboard.")
    closeout_cmd.add_argument("--date", default=None)

    plan_cmd = subparsers.add_parser("adjust-plan", help="Generate weekly and daily dynamic plans into Obsidian.")
    plan_cmd.add_argument("--date", default=None)
    plan_cmd.add_argument("--weekly-only", action="store_true")

    subparsers.add_parser("indexes", help="Rebuild generated indexes.")
    subparsers.add_parser("views", help="Rebuild Obsidian Dataview and Bases-ready views.")
    subparsers.add_parser("rag", help="Build RAG-ready manifest and chunks.")
    subparsers.add_parser("search", help="Build local static search index and page.")
    subparsers.add_parser("normalize", help="Normalize Markdown frontmatter for Dataview/Bases.")
    subparsers.add_parser("verify", help="Verify workstation artifacts.")

    args = parser.parse_args()
    ctx = make_context(args.config)

    if args.command == "init":
        print_results(initialize_workstation(ctx, args.date, args.project, args.task, args.topic))
    elif args.command == "daily":
        print_results(create_daily_note(ctx, args.date))
    elif args.command == "project":
        print_results(
            create_project_status(
                ctx,
                args.name,
                args.date,
                args.project_type,
                args.area,
                args.description,
                args.goal,
            )
        )
    elif args.command == "onboard-project":
        print_results(
            onboard_project(
                ctx,
                args.name,
                args.project_type,
                args.area,
                args.description,
                args.goal,
                args.date,
            )
        )
    elif args.command == "codex-task":
        print_results(create_codex_task_note(ctx, args.date, args.project, args.task, args.summary))
    elif args.command == "knowledge":
        print_results(create_knowledge_card(ctx, args.topic, args.domain))
    elif args.command == "learning":
        print_results(
            create_learning_note(
                ctx,
                args.date,
                args.area,
                args.topic,
                args.summary,
                args.material_source,
                args.project,
            )
        )
    elif args.command == "agent-research":
        print_results(create_agent_research_note(ctx, args.date, args.input_json))
    elif args.command == "document":
        print_results(
            create_document_note(
                ctx,
                args.date,
                args.title,
                args.project,
                args.artifact_path,
                args.audience,
                args.summary,
                args.status,
            )
        )
    elif args.command == "project-log":
        print_results(
            create_project_log(
                ctx,
                args.date,
                args.project,
                args.title,
                args.category,
                args.summary,
                args.decision,
                args.next_step,
            )
        )
    elif args.command == "inbox":
        print_results(append_inbox_entry(ctx, args.title, args.body, args.category, args.source, args.date))
    elif args.command == "review":
        print_results(create_review_note(ctx, args.type, args.date, args.project, args.phase))
    elif args.command == "sync-daily":
        print_results(sync_daily(ctx, args.date))
    elif args.command == "indexes":
        print_results(build_indexes(ctx))
    elif args.command == "views":
        print_results(build_obsidian_views(ctx))
    elif args.command == "rag":
        print_results(build_rag_manifest(ctx))
    elif args.command == "search":
        print_results(build_search_index(ctx))
    elif args.command == "normalize":
        print_results(normalize_metadata(ctx))
    elif args.command == "rebuild":
        print_results(rebuild(ctx, args.date))
    elif args.command == "closeout":
        print_results(daily_closeout(ctx, args.date))
    elif args.command == "adjust-plan":
        print_results(adjust_plan(ctx, args.date, weekly_only=args.weekly_only))
    elif args.command == "verify":
        checks = run_checks(ctx)
        for check in checks:
            marker = "PASS" if check.passed else "FAIL"
            print(f"[{marker}] {check.name}: {check.detail}")
        raise SystemExit(0 if all(check.passed for check in checks) else 1)


if __name__ == "__main__":
    main()
