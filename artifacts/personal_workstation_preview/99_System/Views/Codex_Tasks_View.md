---
type: obsidian-view
id: obsidian-view-codex-tasks
view: codex-tasks
title: "Codex Tasks View"
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

# Codex Tasks View

```dataview
TABLE date, project, task, status, verified, real_execution, network_used, mock, preview, risk
FROM "03_Codex_Tasks"
WHERE type = "codex-task"
SORT date DESC, file.mtime DESC
```
