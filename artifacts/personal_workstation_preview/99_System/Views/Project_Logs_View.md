---
type: obsidian-view
id: obsidian-view-project-logs
view: project-logs
title: "Project Logs View"
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

# Project Logs View

```dataview
TABLE date, project, title, category, status, human_reviewed, updated
FROM "02_Projects"
WHERE type = "project-log"
SORT date DESC, project ASC
```
