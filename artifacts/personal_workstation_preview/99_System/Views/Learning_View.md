---
type: obsidian-view
id: obsidian-view-learning
view: learning
title: "Learning View"
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

# Learning View

```dataview
TABLE date, area, topic, project, status, material_source, human_reviewed, updated
FROM "06_Learning"
WHERE type = "learning-note"
SORT date DESC, area ASC
```
