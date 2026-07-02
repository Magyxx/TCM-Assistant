---
type: obsidian-view
id: obsidian-view-knowledge
view: knowledge
title: "Knowledge View"
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

# Knowledge View

```dataview
TABLE topic, domain, confidence, human_reviewed, updated
FROM "04_Knowledge"
WHERE type = "knowledge-card"
SORT domain ASC, updated DESC
```
