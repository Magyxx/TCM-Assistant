---
type: obsidian-view
id: obsidian-view-projects
view: projects
title: "Projects View"
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

# Projects View

```dataview
TABLE project_id, project_type, area, status, priority, stage, updated
FROM "02_Projects"
WHERE type = "project" AND file.name = "Current_Status"
SORT status ASC, priority DESC, updated DESC
```
