---
type: obsidian-view
id: obsidian-view-pending-review
view: pending-review
title: "Pending Review View"
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

# Pending Review View

```dataview
TABLE type, project, task, topic, status, risk, updated
FROM ""
WHERE human_review_required = true AND human_reviewed = false
SORT risk DESC, updated DESC
```
