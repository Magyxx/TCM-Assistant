# Personal AI Workstation

这是一个本地优先、Obsidian-first、Codex-compatible 的个人 AI 工作站骨架。它的定位不是某个业务项目的笔记系统，而是长期使用的个人知识库、项目管理中枢、Codex 工作流记录器、学习复盘系统和后续多 Agent 调度入口。

## 第一阶段 MVP

本阶段实现：

- 生成 `Personal_AI_Workstation` 风格的目录结构。
- 默认 preview mode，未配置真实 Obsidian vault 时只写入 `artifacts/personal_workstation_preview/`。
- 生成 Daily Note、Codex Task Note、Project Current Status、Knowledge Card。
- 生成 Obsidian Canvas：`00_Home/AI_Workstation.canvas`。
- 生成可视化状态：`workstation_state.json`。
- 生成本地静态 Dashboard：`dashboard.html`。
- 提供 `verify_workstation.py` 自检目录、产物、安全边界和 Dashboard 依赖。

## 安全边界

- 默认 `preview_mode=true`。
- 默认 `allow_overwrite=false`，已有 Markdown 笔记不会被覆盖。
- 不联网，不使用 CDN，不依赖外部服务。
- 不读取 secret。
- 不自动 git commit。
- 不删除用户文件。
- Codex 任务记录默认标注 preview、human_review_required 和真实执行边界。
- 知识卡片默认 `human_reviewed=false`。

## 目录结构

```text
Personal_AI_Workstation/
├─ 00_Home/
│  ├─ Dashboard.md
│  └─ AI_Workstation.canvas
├─ 00_Inbox/
│  └─ Inbox.md
├─ 01_Daily/
├─ 02_Projects/
├─ 03_Codex_Tasks/
├─ 04_Knowledge/
│  ├─ AI/
│  ├─ CS/
│  ├─ Math/
│  ├─ Engineering/
│  ├─ Interview/
│  └─ Work/
├─ 05_Reviews/
│  ├─ Daily/
│  ├─ Weekly/
│  ├─ Monthly/
│  └─ Project_Reviews/
├─ 06_Learning/
│  ├─ Algorithms/
│  ├─ 408/
│  ├─ AI_Infra/
│  ├─ Agent/
│  └─ Papers/
├─ 07_Career/
│  ├─ Internship/
│  ├─ Resume/
│  ├─ Applications/
│  └─ Interview_Prep/
├─ 08_Artifacts/
│  └─ Artifact_Index.md
└─ 99_System/
   ├─ Templates/
   ├─ Schemas/
   └─ Config.md
```

## 使用方式

推荐使用统一 CLI：

```powershell
python -B scripts/personal_workstation/workstation.py init --date 2026-06-12
python -B scripts/personal_workstation/workstation.py daily --date 2026-06-12
python -B scripts/personal_workstation/workstation.py project --name "Personal AI Workstation"
python -B scripts/personal_workstation/workstation.py onboard-project --name "字节短剧互动挑战" --project-type challenge --area project
python -B scripts/personal_workstation/workstation.py codex-task --project "Personal AI Workstation" --task "Bootstrap MVP"
python -B scripts/personal_workstation/workstation.py knowledge --topic "个人 AI 工作站的本地优先知识沉淀" --domain AI
python -B scripts/personal_workstation/workstation.py learning --area Agent --topic "个人知识库工作流打磨" --summary "记录一次学习或实践"
python -B scripts/personal_workstation/workstation.py document --title "Personal AI Workstation 使用流程说明" --project "Personal AI Workstation" --summary "记录一次文档写作"
python -B scripts/personal_workstation/workstation.py project-log --project "Personal AI Workstation" --title "Obsidian 沉淀流程收敛" --summary "记录一次项目细节"
python -B scripts/personal_workstation/workstation.py inbox --title "临时想法" --body "待整理内容"
python -B scripts/personal_workstation/workstation.py review --type weekly --date 2026-06-12
python -B scripts/personal_workstation/workstation.py sync-daily --date 2026-06-12
python -B scripts/personal_workstation/workstation.py normalize
python -B scripts/personal_workstation/workstation.py views
python -B scripts/personal_workstation/workstation.py rag
python -B scripts/personal_workstation/workstation.py search
python -B scripts/personal_workstation/workstation.py closeout --date 2026-06-12
python -B scripts/personal_workstation/workstation.py rebuild --date 2026-06-12
python -B scripts/personal_workstation/workstation.py verify
```

初始化 preview 工作站：

```powershell
python -B scripts/personal_workstation/init_workstation.py
```

生成单个 Daily Note：

```powershell
python -B scripts/personal_workstation/write_daily_note.py --date 2026-06-12
```

生成 Codex 任务记录：

```powershell
python -B scripts/personal_workstation/write_codex_task_note.py --project "Personal AI Workstation" --task "Bootstrap MVP"
```

生成项目状态：

```powershell
python -B scripts/personal_workstation/write_project_status.py --project "Personal AI Workstation"
```

接入已有项目：

```powershell
python -B scripts/personal_workstation/onboard_project.py --name "项目名" --project-type challenge --area project --description "项目说明" --goal "长期目标"
```

生成知识卡片：

```powershell
python -B scripts/personal_workstation/write_knowledge_card.py --topic "个人 AI 工作站的本地优先知识沉淀" --domain AI
```

追加 Inbox 条目：

```powershell
python -B scripts/personal_workstation/write_inbox_entry.py --title "临时想法" --body "待整理内容" --category thought
```

生成复盘笔记：

```powershell
python -B scripts/personal_workstation/write_review_note.py --type weekly --date 2026-06-12
```

生成机器汇总：

```powershell
python -B scripts/personal_workstation/sync_daily.py --date 2026-06-12
```

每日结束一键归档：

```powershell
python -B scripts/personal_workstation/daily_closeout.py --date 2026-06-12
```

重新生成 Dashboard 状态和 HTML：

```powershell
python -B scripts/personal_workstation/build_indexes.py
python -B scripts/personal_workstation/build_obsidian_views.py
python -B scripts/personal_workstation/build_rag_manifest.py
python -B scripts/personal_workstation/build_search_index.py
python -B scripts/personal_workstation/build_dashboard_state.py --date 2026-06-12
python -B scripts/personal_workstation/build_static_dashboard.py --date 2026-06-12
```

验证产物：

```powershell
python -B scripts/personal_workstation/verify_workstation.py
```

## 自动索引

`build_indexes.py` 会生成以下只读式系统索引，默认放在 `99_System/Indexes/`：

- `Project_Index.md`
- `Codex_Task_Index.md`
- `Knowledge_Index.md`
- `Learning_Index.md`
- `Document_Index.md`
- `Project_Log_Index.md`
- `Review_Index.md`
- `Pending_Review_Index.md`

这些索引用于快速回看，也为后续 Dataview、Bases、本地 RAG 和 Dashboard 汇总准备结构化入口。

## Obsidian 查询视图

`build_obsidian_views.py` 会生成：

- `00_Home/Dataview_Dashboard.md`
- `99_System/Views/Projects_View.md`
- `99_System/Views/Codex_Tasks_View.md`
- `99_System/Views/Knowledge_View.md`
- `99_System/Views/Learning_View.md`
- `99_System/Views/Documents_View.md`
- `99_System/Views/Project_Logs_View.md`
- `99_System/Views/Reviews_View.md`
- `99_System/Views/Pending_Review_View.md`
- `99_System/Views/Bases_Ready.md`
- `99_System/Views/bases_ready_view_specs.json`

这些文件不依赖网络。Dataview 查询以 Markdown 代码块形式存在；Bases 部分先生成稳定字段规格和视图映射，不直接写入版本相关的 `.base` 私有格式。

## Daily Closeout

`daily_closeout.py` 是每天结束时的收口命令。它会：

- 确保 Daily Note 存在。
- 生成每日复盘草稿。
- 生成 Daily Sync 机器汇总，不写入 Daily Note 正文。
- 归一化 metadata。
- 刷新系统索引。
- 刷新 Obsidian 查询视图。
- 刷新 RAG-ready manifest 和 chunks。
- 刷新本地静态搜索索引。
- 刷新 `workstation_state.json` 和 `dashboard.html`。

## 日常学习与文档沉淀

当前阶段的重点不是实现真实 RAG，而是让每天的学习、项目细节和文档写作稳定落到 Obsidian：

- 学习记录写入 `06_Learning/{area}/`，用于记录学习目标、输入材料、关键概念、练习、疑问和下一步。
- 文档写作记录写入 `08_Artifacts/Document_Logs/`，用于记录文档目标、读者、产物路径、完成状态和待完善项。
- 项目细节日志写入 `02_Projects/{project}/Logs/`，用于记录临时上下文、关键决策、证据、影响范围和下一步。
- `sync-daily` 会把当天学习、文档、项目日志汇总到 `99_System/Daily_Sync/{date}.md`，并清理 Daily Note 中遗留的自动汇总区块。
- `build_indexes.py` 和 `build_obsidian_views.py` 会生成对应索引与 Dataview 查询。

推荐日常节奏：

```powershell
python -B scripts/personal_workstation/workstation.py learning --area Agent --topic "今天学到的主题" --summary "一句话写清学习目标"
python -B scripts/personal_workstation/workstation.py project-log --project "项目名" --title "今天发生的关键细节" --summary "记录上下文和决策"
python -B scripts/personal_workstation/workstation.py document --title "文档标题" --project "项目名" --artifact-path "docs/example.md" --summary "记录写作目的"
python -B scripts/personal_workstation/workstation.py closeout --date 2026-06-12
```

这些记录都只是 Markdown/frontmatter，不生成 embedding，不调用模型，不写入向量库。后续真正做本地检索时，再根据你的 Obsidian 使用方式决定 embedding 模型、chunk 字段和索引格式。

## RAG-ready 导出

`build_rag_manifest.py` 会生成：

- `99_System/RAG/rag_manifest.json`
- `99_System/RAG/rag_sources.jsonl`
- `99_System/RAG/rag_chunks.jsonl`
- `99_System/RAG/RAG_Sources.md`

这一层只做本地结构化导出，不生成 embedding，不调用模型，不联网。后续接入本地 embedding/RAG 时，应优先读取 `rag_chunks.jsonl`，并用 `preview`、`human_reviewed`、`type`、`project_id` 等字段控制检索范围。

## 本地搜索

`build_search_index.py` 会生成：

- `99_System/Search/search_index.json`
- `99_System/Search/search.html`

`search.html` 是本地静态页面，索引数据内嵌或来自本地 JSON，不依赖 CDN，不请求网络。它用于在正式 RAG 之前快速搜索项目、Codex 任务、学习记录、文档日志、知识卡片和复盘记录。

## Dataview / Bases 字段规范

所有自动生成 Markdown 至少包含：

- `type`
- `id`
- `source`
- `preview`
- `human_review_required`
- `human_reviewed`
- `created`
- `updated`

项目类笔记额外包含：

- `project_id`
- `project`
- `project_type`
- `area`
- `status`
- `priority`
- `stage`

Codex 任务额外包含：

- `date`
- `project`
- `project_id`
- `task`
- `verified`
- `real_execution`
- `network_used`
- `model_weights_trained`
- `mock`
- `dry_run`
- `risk`

学习、文档和项目日志额外包含：

- `area`
- `topic`
- `title`
- `category`
- `artifact_path`
- `audience`
- `material_source`

这些字段是后续 Dataview 查询、Obsidian Bases、本地 embedding 和 RAG 切片的稳定入口。

## 接入真实 Obsidian Vault

复制 `configs/personal_workstation.example.json` 为你的个人配置文件，然后设置：

```json
{
  "preview_mode": false,
  "obsidian_vault_path": "D:/path/to/Personal_AI_Workstation",
  "allow_overwrite": false,
  "safe_append_only": true
}
```

建议先保持 `allow_overwrite=false`。首次接入真实 vault 前，先在 preview 目录完成一次生成和人工检查。

## 接入已有项目

每个已有项目都作为 `02_Projects/{project_name}/` 下的一个模块接入，而不是把工作站写死为该项目的附属工具。

推荐流程：

1. 使用 `write_project_status.py --project "项目名"` 创建项目骨架。
2. 在 `Overview.md` 写清项目定位、背景、边界和产物。
3. 在 `Current_Status.md` 维护当前阶段、进度和下一步。
4. 每次 Codex 工作结束后，用 `write_codex_task_note.py` 生成任务记录，并补全 Changed Files、Generated Artifacts、验证结果和风险边界。
5. 将稳定经验沉淀为 `04_Knowledge/` 知识卡片。
6. 周期性把项目进展汇总到 `05_Reviews/`。

## 长期扩展方向

- 接入 Obsidian Dataview / Bases。
- 接入 Obsidian Git。
- 接入本地 embedding。
- 接入本地 RAG 检索。
- 接入 MCP server。
- 接入多 Agent 工作流。
- 接入每日自动总结。
- 接入周/月复盘自动生成。
- 接入算法题与 408 错题复盘系统。
- 接入求职投递追踪。
- 接入实习项目自动总结。
- 接入论文/文章阅读笔记。
- 接入个人知识图谱。
- 接入任务优先级推荐。
- 接入 Codex 偏离主线报警。
