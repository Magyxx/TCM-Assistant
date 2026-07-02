---
type: obsidian-view
id: obsidian-view-documents
view: documents
title: "Documents View"
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

# Documents View

```dataview
TABLE date, title, project, status, audience, artifact_path, human_reviewed, updated
FROM "08_Artifacts/Document_Logs"
WHERE type = "document-log"
SORT date DESC, file.mtime DESC
```
