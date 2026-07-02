from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.personal_workstation.common import (  # noqa: E402
    WorkstationContext,
    frontmatter,
    json_dump,
    make_context,
    now_iso,
    write_text_file,
)


def view_frontmatter(ctx: WorkstationContext, view_id: str, title: str) -> str:
    timestamp = now_iso(ctx)
    return frontmatter(
        {
            "type": "obsidian-view",
            "id": f"obsidian-view-{view_id}",
            "view": view_id,
            "title": title,
            "source": "personal_workstation.build_obsidian_views",
            "preview": bool(ctx.config.get("preview_mode", True)),
            "human_review_required": False,
            "human_reviewed": True,
            "created": timestamp,
            "updated": timestamp,
        },
        ["view", "dataview", "workstation"],
    )


def dataview_dashboard(ctx: WorkstationContext) -> str:
    return view_frontmatter(ctx, "dashboard", "Dataview Dashboard") + """# Dataview Dashboard

## Active Projects

```dataview
TABLE project_type, area, status, priority, stage, updated
FROM "02_Projects"
WHERE type = "project" AND file.name = "Current_Status"
SORT priority DESC, updated DESC
```

## Recent Codex Tasks

```dataview
TABLE date, project, status, verified, risk, preview
FROM "03_Codex_Tasks"
WHERE type = "codex-task"
SORT date DESC, file.mtime DESC
LIMIT 20
```

## Learning Notes

```dataview
TABLE date, area, project, status, novelty, engineering_value, updated
FROM "06_Learning"
WHERE type = "learning-note" OR type = "agent-research-note"
SORT date DESC, file.mtime DESC
LIMIT 30
```

## Document Logs

```dataview
TABLE date, project, status, artifact_path, updated
FROM "08_Artifacts/Document_Logs"
WHERE type = "document-log"
SORT date DESC, file.mtime DESC
LIMIT 30
```

## Project Detail Logs

```dataview
TABLE date, project, category, status, updated
FROM "02_Projects"
WHERE type = "project-log"
SORT date DESC, file.mtime DESC
LIMIT 30
```

## Pending Human Review

```dataview
TABLE type, project, task, topic, status, updated
FROM ""
WHERE human_review_required = true AND human_reviewed = false
SORT updated DESC
LIMIT 50
```

## Knowledge Cards

```dataview
TABLE domain, confidence, human_reviewed, updated
FROM "04_Knowledge"
WHERE type = "knowledge-card"
SORT updated DESC
```

## Reviews

```dataview
TABLE review_type, period, status, updated
FROM "05_Reviews"
WHERE type = "review"
SORT updated DESC
```
"""


def projects_view(ctx: WorkstationContext) -> str:
    return view_frontmatter(ctx, "projects", "Projects View") + """# Projects View

```dataview
TABLE project_id, project_type, area, status, priority, stage, updated
FROM "02_Projects"
WHERE type = "project" AND file.name = "Current_Status"
SORT status ASC, priority DESC, updated DESC
```
"""


def codex_tasks_view(ctx: WorkstationContext) -> str:
    return view_frontmatter(ctx, "codex-tasks", "Codex Tasks View") + """# Codex Tasks View

```dataview
TABLE date, project, task, status, verified, real_execution, network_used, mock, preview, risk
FROM "03_Codex_Tasks"
WHERE type = "codex-task"
SORT date DESC, file.mtime DESC
```
"""


def knowledge_view(ctx: WorkstationContext) -> str:
    return view_frontmatter(ctx, "knowledge", "Knowledge View") + """# Knowledge View

```dataview
TABLE topic, domain, confidence, human_reviewed, updated
FROM "04_Knowledge"
WHERE type = "knowledge-card"
SORT domain ASC, updated DESC
```
"""


def learning_view(ctx: WorkstationContext) -> str:
    return view_frontmatter(ctx, "learning", "Learning View") + """# Learning View

```dataview
TABLE date, area, topic, project, status, novelty, engineering_value, material_source, human_reviewed, updated
FROM "06_Learning"
WHERE type = "learning-note" OR type = "agent-research-note"
SORT date DESC, area ASC
```
"""


def documents_view(ctx: WorkstationContext) -> str:
    return view_frontmatter(ctx, "documents", "Documents View") + """# Documents View

```dataview
TABLE date, title, project, status, audience, artifact_path, human_reviewed, updated
FROM "08_Artifacts/Document_Logs"
WHERE type = "document-log"
SORT date DESC, file.mtime DESC
```
"""


def project_logs_view(ctx: WorkstationContext) -> str:
    return view_frontmatter(ctx, "project-logs", "Project Logs View") + """# Project Logs View

```dataview
TABLE date, project, title, category, status, human_reviewed, updated
FROM "02_Projects"
WHERE type = "project-log"
SORT date DESC, project ASC
```
"""


def reviews_view(ctx: WorkstationContext) -> str:
    return view_frontmatter(ctx, "reviews", "Reviews View") + """# Reviews View

```dataview
TABLE review_type, period, project, phase, status, human_reviewed, updated
FROM "05_Reviews"
WHERE type = "review"
SORT period DESC
```
"""


def pending_review_view(ctx: WorkstationContext) -> str:
    return view_frontmatter(ctx, "pending-review", "Pending Review View") + """# Pending Review View

```dataview
TABLE type, project, task, topic, status, risk, updated
FROM ""
WHERE human_review_required = true AND human_reviewed = false
SORT risk DESC, updated DESC
```
"""


def bases_ready_note(ctx: WorkstationContext) -> str:
    return view_frontmatter(ctx, "bases-ready", "Bases Ready Specification") + """# Bases Ready Specification

This workstation is Bases-ready through stable frontmatter fields. Keep generated data in Markdown/frontmatter first, then map Obsidian Bases views onto the same fields after confirming the local Obsidian version and Bases format.

## Recommended Bases

| Base | Source | Filter |
| --- | --- | --- |
| Projects | `02_Projects` | `type = project` |
| Codex Tasks | `03_Codex_Tasks` | `type = codex-task` |
| Knowledge | `04_Knowledge` | `type = knowledge-card` |
| Learning | `06_Learning` | `type = learning-note` |
| Documents | `08_Artifacts/Document_Logs` | `type = document-log` |
| Project Logs | `02_Projects` | `type = project-log` |
| Reviews | `05_Reviews` | `type = review` |
| Pending Review | all notes | `human_review_required = true AND human_reviewed = false` |

## Stable Fields

- `type`
- `id`
- `project_id`
- `project`
- `topic`
- `title`
- `status`
- `area`
- `category`
- `artifact_path`
- `priority`
- `stage`
- `date`
- `period`
- `verified`
- `risk`
- `human_review_required`
- `human_reviewed`
- `created`
- `updated`
"""


def bases_specs(ctx: WorkstationContext) -> dict:
    return {
        "generated_at": now_iso(ctx),
        "source": "personal_workstation.build_obsidian_views",
        "preview": bool(ctx.config.get("preview_mode", True)),
        "bases_ready": True,
        "note": "This is a neutral local spec, not a version-specific Obsidian .base file.",
        "views": [
            {
                "name": "Projects",
                "source": "02_Projects",
                "filter": {"type": "project", "file_name": "Current_Status"},
                "columns": ["project", "project_type", "area", "status", "priority", "stage", "updated"],
            },
            {
                "name": "Codex Tasks",
                "source": "03_Codex_Tasks",
                "filter": {"type": "codex-task"},
                "columns": ["date", "project", "task", "status", "verified", "risk", "preview"],
            },
            {
                "name": "Knowledge",
                "source": "04_Knowledge",
                "filter": {"type": "knowledge-card"},
                "columns": ["topic", "domain", "confidence", "human_reviewed", "updated"],
            },
            {
                "name": "Learning",
                "source": "06_Learning",
                "filter": {"type": "learning-note"},
                "columns": ["date", "area", "topic", "project", "status", "updated"],
            },
            {
                "name": "Documents",
                "source": "08_Artifacts/Document_Logs",
                "filter": {"type": "document-log"},
                "columns": ["date", "title", "project", "status", "artifact_path", "updated"],
            },
            {
                "name": "Project Logs",
                "source": "02_Projects",
                "filter": {"type": "project-log"},
                "columns": ["date", "project", "title", "category", "status", "updated"],
            },
            {
                "name": "Reviews",
                "source": "05_Reviews",
                "filter": {"type": "review"},
                "columns": ["review_type", "period", "project", "status", "updated"],
            },
            {
                "name": "Pending Review",
                "source": "",
                "filter": {"human_review_required": True, "human_reviewed": False},
                "columns": ["type", "project", "task", "topic", "status", "risk", "updated"],
            },
        ],
    }


def build_obsidian_views(ctx: WorkstationContext):
    home = ctx.target_root / "00_Home"
    views = ctx.target_root / "99_System" / "Views"
    specs = {
        home / "Dataview_Dashboard.md": dataview_dashboard(ctx),
        views / "Projects_View.md": projects_view(ctx),
        views / "Codex_Tasks_View.md": codex_tasks_view(ctx),
        views / "Knowledge_View.md": knowledge_view(ctx),
        views / "Learning_View.md": learning_view(ctx),
        views / "Documents_View.md": documents_view(ctx),
        views / "Project_Logs_View.md": project_logs_view(ctx),
        views / "Reviews_View.md": reviews_view(ctx),
        views / "Pending_Review_View.md": pending_review_view(ctx),
        views / "Bases_Ready.md": bases_ready_note(ctx),
        views / "bases_ready_view_specs.json": json_dump(bases_specs(ctx)),
    }
    results = []
    for path, content in specs.items():
        results.append(write_text_file(path, content, overwrite=True))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Obsidian Dataview and Bases-ready views.")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    ctx = make_context(args.config)
    for result in build_obsidian_views(ctx):
        print(f"{result.action}: {result.path}")


if __name__ == "__main__":
    main()
