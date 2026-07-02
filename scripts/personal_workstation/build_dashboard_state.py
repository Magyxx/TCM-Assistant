from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.personal_workstation.common import (  # noqa: E402
    CAREER_DIRS,
    LEARNING_DIRS,
    MANAGED_TOP_LEVELS,
    WorkstationContext,
    configured_path,
    json_dump,
    make_context,
    markdown_files,
    now_iso,
    read_frontmatter,
    relative_to_target,
    today_string,
    write_text_file,
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _project_progress(status_path: Path) -> int:
    match = re.search(r"progress:\s*(\d+)%", _read_text(status_path))
    if not match:
        return 0
    return max(0, min(100, int(match.group(1))))


def _is_managed_path(ctx: WorkstationContext, path: Path) -> bool:
    try:
        rel = path.relative_to(ctx.target_root)
    except ValueError:
        return False
    return bool(rel.parts) and rel.parts[0] in MANAGED_TOP_LEVELS


def resolve_dashboard_date(ctx: WorkstationContext, note_date: str | None = None) -> str:
    if note_date:
        return note_date
    configured_today = today_string(ctx)
    daily_root = configured_path(ctx, "daily_dir")
    if (daily_root / f"{configured_today}.md").exists():
        return configured_today
    daily_dates = sorted(path.stem for path in daily_root.glob("*.md")) if daily_root.exists() else []
    return daily_dates[-1] if daily_dates else configured_today


def collect_state(ctx: WorkstationContext, note_date: str | None = None) -> dict:
    today = resolve_dashboard_date(ctx, note_date)
    daily_note = configured_path(ctx, "daily_dir") / f"{today}.md"
    project_root = configured_path(ctx, "projects_dir")
    codex_root = configured_path(ctx, "codex_tasks_dir")
    knowledge_root = configured_path(ctx, "knowledge_dir")
    reviews_root = configured_path(ctx, "reviews_dir")
    learning_root = ctx.target_root / "06_Learning"
    document_root = ctx.target_root / "08_Artifacts" / "Document_Logs"
    indexes_root = ctx.target_root / "99_System" / "Indexes"
    views_root = ctx.target_root / "99_System" / "Views"
    rag_root = ctx.target_root / "99_System" / "RAG"
    search_root = ctx.target_root / "99_System" / "Search"

    projects = []
    if project_root.exists():
        for project_dir in sorted(p for p in project_root.iterdir() if p.is_dir()):
            status_path = project_dir / "Current_Status.md"
            front = read_frontmatter(status_path) if status_path.exists() else {}
            projects.append(
                {
                    "name": front.get("project", project_dir.name),
                    "status": front.get("status", "unknown"),
                    "priority": front.get("priority", "medium"),
                    "stage": front.get("stage", "unknown"),
                    "progress": _project_progress(status_path),
                    "path": relative_to_target(ctx, status_path),
                }
            )

    codex_tasks = []
    for path in sorted(markdown_files(codex_root), key=lambda item: item.stat().st_mtime, reverse=True)[:8]:
        front = read_frontmatter(path)
        codex_tasks.append(
            {
                "task": front.get("task", path.stem),
                "project": front.get("project", "unknown"),
                "date": front.get("date", ""),
                "status": front.get("status", "unknown"),
                "verified": bool(front.get("verified", False)),
                "risk": front.get("risk", "unknown"),
                "preview": bool(front.get("preview", True)),
                "path": relative_to_target(ctx, path),
            }
        )

    knowledge_cards = markdown_files(knowledge_root)
    review_notes = markdown_files(reviews_root)
    learning_note_types = {"learning-note", "agent-research-note"}
    learning_notes = [path for path in markdown_files(learning_root) if read_frontmatter(path).get("type") in learning_note_types]
    document_logs = [path for path in markdown_files(document_root) if read_frontmatter(path).get("type") == "document-log"]
    project_log_notes = [
        path for path in markdown_files(project_root) if read_frontmatter(path).get("type") == "project-log"
    ]
    index_files = markdown_files(indexes_root)
    view_notes = markdown_files(views_root)
    rag_manifest_path = rag_root / "rag_manifest.json"
    search_index_path = search_root / "search_index.json"
    rag_counts = {"rag_sources": 0, "rag_chunks": 0, "search_records": 0}
    if rag_manifest_path.exists():
        try:
            rag_manifest = json.loads(rag_manifest_path.read_text(encoding="utf-8"))
            rag_counts["rag_sources"] = int(rag_manifest.get("source_count", 0))
            rag_counts["rag_chunks"] = int(rag_manifest.get("chunk_count", 0))
        except Exception:
            pass
    if search_index_path.exists():
        try:
            search_index = json.loads(search_index_path.read_text(encoding="utf-8"))
            rag_counts["search_records"] = int(search_index.get("index", {}).get("record_count", 0))
        except Exception:
            pass

    recent_learning_notes = []
    for path in sorted(learning_notes, key=lambda item: item.stat().st_mtime, reverse=True)[:8]:
        front = read_frontmatter(path)
        recent_learning_notes.append(
            {
                "topic": front.get("topic", path.stem),
                "area": front.get("area", path.parent.name),
                "project": front.get("project", "none"),
                "date": front.get("date", ""),
                "status": front.get("novelty") or front.get("status", "unknown"),
                "type": front.get("type", "learning-note"),
                "path": relative_to_target(ctx, path),
            }
        )

    recent_document_logs = []
    for path in sorted(document_logs, key=lambda item: item.stat().st_mtime, reverse=True)[:8]:
        front = read_frontmatter(path)
        recent_document_logs.append(
            {
                "title": front.get("title", path.stem),
                "project": front.get("project", "none"),
                "date": front.get("date", ""),
                "status": front.get("status", "unknown"),
                "artifact_path": front.get("artifact_path", "none"),
                "path": relative_to_target(ctx, path),
            }
        )

    recent_project_logs = []
    for path in sorted(project_log_notes, key=lambda item: item.stat().st_mtime, reverse=True)[:8]:
        front = read_frontmatter(path)
        recent_project_logs.append(
            {
                "title": front.get("title", path.stem),
                "project": front.get("project", "unknown"),
                "date": front.get("date", ""),
                "category": front.get("category", "progress"),
                "status": front.get("status", "unknown"),
                "path": relative_to_target(ctx, path),
            }
        )

    pending_review = []
    risk_items = []
    for path in markdown_files(ctx.target_root):
        if not _is_managed_path(ctx, path):
            continue
        front = read_frontmatter(path)
        if front.get("human_review_required") is True or front.get("human_reviewed") is False:
            pending_review.append(
                {
                    "title": front.get("task") or front.get("topic") or front.get("project") or path.stem,
                    "type": front.get("type", "markdown"),
                    "path": relative_to_target(ctx, path),
                }
            )
        if str(front.get("risk", "")).lower() in {"medium", "high"}:
            risk_items.append(
                {
                    "title": front.get("task") or path.stem,
                    "risk": front.get("risk"),
                    "path": relative_to_target(ctx, path),
                }
            )

    generated_candidates = [
        ctx.target_root / "00_Home" / "AI_Workstation.canvas",
        ctx.target_root / "dashboard.html",
        ctx.target_root / "workstation_state.json",
        ctx.target_root / "08_Artifacts" / "Artifact_Index.md",
        indexes_root / "Project_Index.md",
        indexes_root / "Codex_Task_Index.md",
        indexes_root / "Knowledge_Index.md",
        indexes_root / "Learning_Index.md",
        indexes_root / "Document_Index.md",
        indexes_root / "Project_Log_Index.md",
        indexes_root / "Review_Index.md",
        indexes_root / "Pending_Review_Index.md",
        ctx.target_root / "00_Home" / "Dataview_Dashboard.md",
        views_root / "Projects_View.md",
        views_root / "Codex_Tasks_View.md",
        views_root / "Knowledge_View.md",
        views_root / "Learning_View.md",
        views_root / "Documents_View.md",
        views_root / "Project_Logs_View.md",
        views_root / "Reviews_View.md",
        views_root / "Pending_Review_View.md",
        views_root / "Bases_Ready.md",
        views_root / "bases_ready_view_specs.json",
        rag_root / "RAG_Sources.md",
        rag_root / "rag_manifest.json",
        rag_root / "rag_sources.jsonl",
        rag_root / "rag_chunks.jsonl",
        search_root / "search.html",
        search_root / "search_index.json",
    ]
    recent_markdown = sorted(markdown_files(ctx.target_root), key=lambda item: item.stat().st_mtime, reverse=True)[:6]
    recent_artifacts_raw = [
        {"name": path.name, "path": relative_to_target(ctx, path)}
        for path in generated_candidates
        if path.exists()
    ] + [{"name": path.name, "path": relative_to_target(ctx, path)} for path in recent_markdown]
    recent_artifacts = []
    seen_artifacts = set()
    for artifact in recent_artifacts_raw:
        if artifact["path"] in seen_artifacts:
            continue
        seen_artifacts.add(artifact["path"])
        recent_artifacts.append(artifact)

    return {
        "generated_at": now_iso(ctx),
        "preview_mode": bool(ctx.config.get("preview_mode", True)),
        "vault_root": str(ctx.target_root),
        "today": today,
        "today_overview": {
            "daily_note": relative_to_target(ctx, daily_note),
            "daily_note_exists": daily_note.exists(),
            "focus": "建立个人 AI 工作站第一阶段 MVP",
            "codex_tasks_today": sum(1 for item in codex_tasks if item.get("date") == today),
            "learning_notes_today": sum(1 for path in learning_notes if str(read_frontmatter(path).get("date", "")) == today),
            "document_logs_today": sum(1 for path in document_logs if str(read_frontmatter(path).get("date", "")) == today),
            "project_logs_today": sum(1 for path in project_log_notes if str(read_frontmatter(path).get("date", "")) == today),
        },
        "counts": {
            "active_projects": len(projects),
            "codex_tasks": len(markdown_files(codex_root)),
            "knowledge_cards": len(knowledge_cards),
            "learning_notes": len(learning_notes),
            "document_logs": len(document_logs),
            "project_logs": len(project_log_notes),
            "review_notes": len(review_notes),
            "system_indexes": len(index_files),
            "obsidian_views": len(view_notes),
            "rag_sources": rag_counts["rag_sources"],
            "rag_chunks": rag_counts["rag_chunks"],
            "search_records": rag_counts["search_records"],
            "pending_review": len(pending_review),
            "risk_items": len(risk_items),
        },
        "active_projects": projects,
        "recent_codex_tasks": codex_tasks,
        "recent_learning_notes": recent_learning_notes,
        "recent_document_logs": recent_document_logs,
        "recent_project_logs": recent_project_logs,
        "pending_review": pending_review[:12],
        "risk_status": {
            "level": "medium" if risk_items else "low",
            "items": risk_items[:8],
            "note": "所有自动生成结论默认需要人工复核。",
        },
        "learning_modules": [
            {
                "name": name,
                "path": f"06_Learning/{name}/",
                "status": "ready",
                "note_count": sum(1 for path in learning_notes if path.parent.name == name),
            }
            for name in LEARNING_DIRS
        ],
        "career_modules": [
            {"name": name, "path": f"07_Career/{name}/", "status": "ready"} for name in CAREER_DIRS
        ],
        "recent_artifacts": recent_artifacts[:12],
        "next_actions": [
            "确认真实 Obsidian vault 路径后再关闭 preview mode。",
            "把当前长期项目逐个登记到 02_Projects/。",
            "每天至少落一条学习记录、一条项目细节或一条文档写作记录。",
            "稳定结论再沉淀为知识卡片；embedding 和真实 RAG 格式后续再定。",
        ],
        "paths": {
            "dashboard": "dashboard.html",
            "state": "workstation_state.json",
            "canvas": "00_Home/AI_Workstation.canvas",
            "inbox": "00_Inbox/Inbox.md",
            "learning": "06_Learning/",
            "document_logs": "08_Artifacts/Document_Logs/",
            "project_logs": "02_Projects/",
            "artifacts": "08_Artifacts/Artifact_Index.md",
            "indexes": "99_System/Indexes/",
            "views": "99_System/Views/",
            "dataview_dashboard": "00_Home/Dataview_Dashboard.md",
            "rag": "99_System/RAG/",
            "search": "99_System/Search/search.html",
        },
        "audit": {
            "source": "personal_workstation.build_dashboard_state",
            "network_used": False,
            "external_services": False,
            "model_weights_trained": False,
            "automatic_vcs_commit": False,
            "secrets_read": False,
            "human_review_required": True,
        },
    }


def build_dashboard_state(ctx: WorkstationContext, note_date: str | None = None):
    state = collect_state(ctx, note_date)
    path = ctx.target_root / "workstation_state.json"
    return write_text_file(path, json_dump(state), overwrite=True), state


def main() -> None:
    parser = argparse.ArgumentParser(description="Build workstation_state.json.")
    parser.add_argument("--config", default=None)
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    ctx = make_context(args.config)
    result, _ = build_dashboard_state(ctx, args.date)
    print(f"{result.action}: {result.path}")


if __name__ == "__main__":
    main()
