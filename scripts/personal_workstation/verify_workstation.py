from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.personal_workstation.common import (  # noqa: E402
    MANAGED_TOP_LEVELS,
    REQUIRED_DIRECTORIES,
    WorkstationContext,
    configured_path,
    load_config,
    make_context,
    markdown_files,
    read_frontmatter,
)


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


def _exists_any(root: Path, pattern: str) -> bool:
    return root.exists() and any(root.rglob(pattern))


def _scan_text_files(root: Path, patterns: list[str]) -> list[str]:
    hits: list[str] = []
    if not root.exists():
        return hits
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".md", ".json", ".html", ".canvas"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                hits.append(str(path))
                break
    return hits


def _is_managed_path(ctx: WorkstationContext, path: Path) -> bool:
    try:
        rel = path.relative_to(ctx.target_root)
    except ValueError:
        return False
    return bool(rel.parts) and rel.parts[0] in MANAGED_TOP_LEVELS


def _network_dependency_hits(ctx: WorkstationContext) -> list[str]:
    hits: list[str] = []
    dashboard = ctx.target_root / "dashboard.html"
    if dashboard.exists():
        text = dashboard.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"https?://|cdn\.|<script\s+src=|<link[^>]+https?://", text, re.IGNORECASE):
            hits.append(str(dashboard))
    for path in (ctx.repo_root / "scripts" / "personal_workstation").glob("*.py"):
        if path.name == "verify_workstation.py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"\b(requests|urllib|socket|http\.client)\b", text):
            hits.append(str(path))
    return hits


def _git_commit_hits(ctx: WorkstationContext) -> list[str]:
    hits: list[str] = []
    for path in (ctx.repo_root / "scripts" / "personal_workstation").glob("*.py"):
        if path.name == "verify_workstation.py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        if re.search(r"(subprocess\.\w+|os\.system|os\.popen)\s*\([^)]*git\s+commit", text, re.DOTALL):
            hits.append(str(path))
    return hits


def run_checks(ctx: WorkstationContext) -> list[Check]:
    config_path, config = load_config(ctx.config_path)
    checks: list[Check] = []
    checks.append(Check("config_exists", config_path.exists(), str(config_path)))
    if config_path.name.endswith(".example.json"):
        preview_ok = config.get("preview_mode") is True
        preview_detail = str(config.get("preview_mode"))
    else:
        preview_ok = isinstance(config.get("preview_mode"), bool)
        preview_detail = f"configured={config.get('preview_mode')}"
    checks.append(Check("preview_mode_configured", preview_ok, preview_detail))

    missing_dirs = [rel for rel in REQUIRED_DIRECTORIES if not (ctx.target_root / rel).exists()]
    checks.append(Check("required_directories", not missing_dirs, ", ".join(missing_dirs) or "ok"))

    daily_exists = _exists_any(configured_path(ctx, "daily_dir"), "*.md")
    checks.append(Check("daily_note_exists", daily_exists, str(configured_path(ctx, "daily_dir"))))

    codex_exists = _exists_any(configured_path(ctx, "codex_tasks_dir"), "*.md")
    checks.append(Check("codex_task_note_exists", codex_exists, str(configured_path(ctx, "codex_tasks_dir"))))

    project_status_exists = _exists_any(configured_path(ctx, "projects_dir"), "Current_Status.md")
    checks.append(Check("project_status_exists", project_status_exists, str(configured_path(ctx, "projects_dir"))))

    knowledge_exists = bool(markdown_files(configured_path(ctx, "knowledge_dir")))
    checks.append(Check("knowledge_card_exists", knowledge_exists, str(configured_path(ctx, "knowledge_dir"))))

    review_exists = bool(markdown_files(configured_path(ctx, "reviews_dir")))
    checks.append(Check("review_note_exists", review_exists, str(configured_path(ctx, "reviews_dir"))))

    learning_areas = ["算法", "Agent", "项目", "工程能力"]
    missing_learning_areas = [
        area for area in learning_areas if not (ctx.target_root / "06_Learning" / area / "Index.md").exists()
    ]
    checks.append(Check("learning_areas_exist", not missing_learning_areas, ", ".join(missing_learning_areas) or "ok"))

    document_dir_exists = (ctx.target_root / "08_Artifacts" / "Document_Logs").exists()
    checks.append(Check("document_log_dir_exists", document_dir_exists, str(ctx.target_root / "08_Artifacts" / "Document_Logs")))

    project_logs_ready = any((path.parent / "Logs").exists() or path.name == "Current_Status.md" for path in configured_path(ctx, "projects_dir").rglob("Current_Status.md"))
    checks.append(Check("project_logs_ready", project_logs_ready, str(configured_path(ctx, "projects_dir"))))

    cli_path = ctx.repo_root / "scripts" / "personal_workstation" / "workstation.py"
    checks.append(Check("unified_cli_exists", cli_path.exists(), str(cli_path)))

    required_scripts = {
        "onboard_project.py",
        "sync_daily.py",
        "normalize_metadata.py",
        "build_indexes.py",
        "build_obsidian_views.py",
        "build_rag_manifest.py",
        "build_search_index.py",
        "daily_closeout.py",
        "plan_automation.py",
        "write_inbox_entry.py",
        "write_review_note.py",
        "write_learning_note.py",
        "write_agent_research_note.py",
        "write_document_note.py",
        "write_project_log.py",
    }
    script_dir = ctx.repo_root / "scripts" / "personal_workstation"
    missing_scripts = sorted(name for name in required_scripts if not (script_dir / name).exists())
    checks.append(Check("long_term_scripts_exist", not missing_scripts, ", ".join(missing_scripts) or "ok"))

    index_dir = ctx.target_root / "99_System" / "Indexes"
    required_indexes = {
        "Project_Index.md",
        "Codex_Task_Index.md",
        "Knowledge_Index.md",
        "Learning_Index.md",
        "Document_Index.md",
        "Project_Log_Index.md",
        "Review_Index.md",
        "Pending_Review_Index.md",
    }
    missing_indexes = sorted(name for name in required_indexes if not (index_dir / name).exists())
    checks.append(Check("system_indexes_exist", not missing_indexes, ", ".join(missing_indexes) or "ok"))

    views_dir = ctx.target_root / "99_System" / "Views"
    required_views = {
        "Projects_View.md",
        "Codex_Tasks_View.md",
        "Knowledge_View.md",
        "Learning_View.md",
        "Documents_View.md",
        "Project_Logs_View.md",
        "Reviews_View.md",
        "Pending_Review_View.md",
        "Bases_Ready.md",
        "bases_ready_view_specs.json",
    }
    missing_views = sorted(name for name in required_views if not (views_dir / name).exists())
    home_dataview = ctx.target_root / "00_Home" / "Dataview_Dashboard.md"
    if not home_dataview.exists():
        missing_views.append("00_Home/Dataview_Dashboard.md")
    checks.append(Check("obsidian_views_exist", not missing_views, ", ".join(missing_views) or "ok"))

    dataview_files = [home_dataview] + [views_dir / name for name in required_views if name.endswith(".md")]
    missing_dataview_blocks = [
        str(path)
        for path in dataview_files
        if path.exists() and path.name != "Bases_Ready.md" and "```dataview" not in path.read_text(encoding="utf-8", errors="ignore")
    ]
    checks.append(Check("dataview_blocks_exist", not missing_dataview_blocks, ", ".join(missing_dataview_blocks) or "ok"))

    bases_spec_path = views_dir / "bases_ready_view_specs.json"
    bases_spec_ok = False
    bases_spec_detail = str(bases_spec_path)
    if bases_spec_path.exists():
        try:
            bases_spec = json.loads(bases_spec_path.read_text(encoding="utf-8"))
            bases_spec_ok = bool(bases_spec.get("bases_ready")) and isinstance(bases_spec.get("views"), list)
            bases_spec_detail = f"views={len(bases_spec.get('views', []))}"
        except json.JSONDecodeError as exc:
            bases_spec_detail = str(exc)
    checks.append(Check("bases_ready_spec_valid", bases_spec_ok, bases_spec_detail))

    rag_dir = ctx.target_root / "99_System" / "RAG"
    required_rag = {"rag_manifest.json", "rag_sources.jsonl", "rag_chunks.jsonl", "RAG_Sources.md"}
    missing_rag = sorted(name for name in required_rag if not (rag_dir / name).exists())
    checks.append(Check("rag_manifest_exists", not missing_rag, ", ".join(missing_rag) or "ok"))

    rag_manifest_ok = False
    rag_manifest_detail = str(rag_dir / "rag_manifest.json")
    if (rag_dir / "rag_manifest.json").exists():
        try:
            rag_manifest = json.loads((rag_dir / "rag_manifest.json").read_text(encoding="utf-8"))
            rag_manifest_ok = (
                rag_manifest.get("embedding_generated") is False
                and rag_manifest.get("network_used") is False
                and int(rag_manifest.get("source_count", 0)) > 0
                and int(rag_manifest.get("chunk_count", 0)) > 0
            )
            rag_manifest_detail = f"sources={rag_manifest.get('source_count')}, chunks={rag_manifest.get('chunk_count')}"
        except Exception as exc:
            rag_manifest_detail = str(exc)
    checks.append(Check("rag_manifest_valid", rag_manifest_ok, rag_manifest_detail))

    chunks_ok = False
    chunks_detail = str(rag_dir / "rag_chunks.jsonl")
    if (rag_dir / "rag_chunks.jsonl").exists():
        try:
            first_line = (rag_dir / "rag_chunks.jsonl").read_text(encoding="utf-8").splitlines()[0]
            first_chunk = json.loads(first_line)
            chunks_ok = {"chunk_id", "source_id", "path", "text"} <= set(first_chunk)
            chunks_detail = "ok" if chunks_ok else f"keys={sorted(first_chunk)}"
        except Exception as exc:
            chunks_detail = str(exc)
    checks.append(Check("rag_chunks_jsonl_valid", chunks_ok, chunks_detail))

    search_dir = ctx.target_root / "99_System" / "Search"
    search_index_path = search_dir / "search_index.json"
    search_html_path = search_dir / "search.html"
    search_ok = False
    search_detail = str(search_index_path)
    if search_index_path.exists():
        try:
            search_index = json.loads(search_index_path.read_text(encoding="utf-8"))
            search_ok = int(search_index.get("index", {}).get("record_count", 0)) > 0 and isinstance(search_index.get("records"), list)
            search_detail = f"records={search_index.get('index', {}).get('record_count')}"
        except Exception as exc:
            search_detail = str(exc)
    checks.append(Check("search_index_valid", search_ok, search_detail))
    checks.append(Check("search_html_exists", search_html_path.exists(), str(search_html_path)))

    canvas = ctx.target_root / "00_Home" / "AI_Workstation.canvas"
    canvas_ok = False
    canvas_detail = str(canvas)
    if canvas.exists():
        try:
            data = json.loads(canvas.read_text(encoding="utf-8"))
            canvas_ok = isinstance(data.get("nodes"), list) and len(data["nodes"]) >= 11 and isinstance(data.get("edges"), list)
            canvas_detail = f"nodes={len(data.get('nodes', []))}, edges={len(data.get('edges', []))}"
        except json.JSONDecodeError as exc:
            canvas_detail = str(exc)
    checks.append(Check("canvas_valid_json", canvas_ok, canvas_detail))

    state_path = ctx.target_root / "workstation_state.json"
    required_state = {
        "generated_at",
        "preview_mode",
        "vault_root",
        "today",
        "today_overview",
        "counts",
        "active_projects",
        "recent_codex_tasks",
        "recent_learning_notes",
        "recent_document_logs",
        "recent_project_logs",
        "pending_review",
        "risk_status",
        "learning_modules",
        "career_modules",
        "recent_artifacts",
        "next_actions",
        "paths",
        "audit",
    }
    state_ok = False
    state_detail = str(state_path)
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            missing = sorted(required_state - set(state))
            state_ok = not missing
            state_detail = "ok" if state_ok else f"missing={missing}"
        except json.JSONDecodeError as exc:
            state_detail = str(exc)
    checks.append(Check("workstation_state_complete", state_ok, state_detail))

    dashboard = ctx.target_root / "dashboard.html"
    checks.append(Check("dashboard_exists", dashboard.exists(), str(dashboard)))

    metadata_required = {"type", "id", "source", "preview", "human_review_required", "human_reviewed", "created", "updated"}
    metadata_missing = []
    for path in markdown_files(ctx.target_root):
        if not _is_managed_path(ctx, path):
            continue
        front = read_frontmatter(path)
        missing = metadata_required - set(front)
        if missing:
            metadata_missing.append(f"{path}: {sorted(missing)}")
    checks.append(Check("dataview_ready_frontmatter", not metadata_missing, "; ".join(metadata_missing[:5]) or "ok"))

    secret_hits = _scan_text_files(ctx.target_root, [r"sk-[A-Za-z0-9]{20,}", r"api[_-]?key\s*[:=]", r"password\s*[:=]", r"BEGIN PRIVATE KEY"])
    checks.append(Check("no_secret_material", not secret_hits, ", ".join(secret_hits) or "ok"))

    network_hits = _network_dependency_hits(ctx)
    checks.append(Check("no_network_dependencies", not network_hits, ", ".join(network_hits) or "ok"))

    git_hits = _git_commit_hits(ctx)
    checks.append(Check("no_automatic_git_commit", not git_hits, ", ".join(git_hits) or "ok"))

    allowed_top_levels = {"configs", "scripts", "docs", "artifacts"}
    unexpected = [
        item.name
        for item in ctx.repo_root.iterdir()
        if item.name not in allowed_top_levels and not item.name.startswith(".")
    ]
    checks.append(Check("no_core_business_logic_modified", not unexpected, ", ".join(unexpected) or "ok"))

    pycache_dirs = [str(path) for path in ctx.repo_root.rglob("__pycache__")]
    checks.append(Check("no_python_cache_artifacts", not pycache_dirs, ", ".join(pycache_dirs) or "ok"))
    return checks


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Personal AI Workstation MVP artifacts.")
    parser.add_argument("--config", default=None)
    parser.add_argument("--json", action="store_true", help="Emit JSON result.")
    args = parser.parse_args()
    ctx = make_context(args.config)
    checks = run_checks(ctx)
    passed = all(check.passed for check in checks)
    if args.json:
        print(
            json.dumps(
                {
                    "passed": passed,
                    "target_root": str(ctx.target_root),
                    "checks": [check.__dict__ for check in checks],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"target_root: {ctx.target_root}")
        for check in checks:
            marker = "PASS" if check.passed else "FAIL"
            print(f"[{marker}] {check.name}: {check.detail}")
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
