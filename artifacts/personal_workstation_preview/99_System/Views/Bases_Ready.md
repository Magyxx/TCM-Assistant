---
type: obsidian-view
id: obsidian-view-bases-ready
view: bases-ready
title: "Bases Ready Specification"
source: personal_workstation.build_obsidian_views
preview: true
human_review_required: false
human_reviewed: true
created: "2026-06-11T19:41:12-07:00"
updated: "2026-06-11T19:41:12-07:00"
tags:
  - view
  - dataview
  - workstation
---

# Bases Ready Specification

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
