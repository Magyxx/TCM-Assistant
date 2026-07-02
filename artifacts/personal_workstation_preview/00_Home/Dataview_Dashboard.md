---
type: obsidian-view
id: obsidian-view-dashboard
view: dashboard
title: "Dataview Dashboard"
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

# Dataview Dashboard

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
TABLE date, area, project, status, updated
FROM "06_Learning"
WHERE type = "learning-note"
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
