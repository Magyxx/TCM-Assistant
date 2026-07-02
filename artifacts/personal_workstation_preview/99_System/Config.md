---
type: system-config
status: active
source: personal_workstation.init_workstation
preview: true
human_review_required: true
human_reviewed: false
created: 2026-06-11
updated: 2026-06-11
id: system-config-config
tags:
  - system
  - workstation
---

# Workstation Config

## 当前模式
- preview_mode: true
- target_root: `D:\code\obsidian\artifacts\personal_workstation_preview`
- allow_overwrite: false
- safe_append_only: true

## 安全边界
- 不读取 secret。
- 不联网。
- 不自动 git commit。
- 不删除用户文件。
- 默认不覆盖已有 Obsidian 笔记。
