---
type: obsidian-view
id: obsidian-view-reviews
view: reviews
title: "Reviews View"
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

# Reviews View

```dataview
TABLE review_type, period, project, phase, status, human_reviewed, updated
FROM "05_Reviews"
WHERE type = "review"
SORT period DESC
```
