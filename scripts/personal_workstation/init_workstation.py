from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.personal_workstation.build_canvas import build_canvas  # noqa: E402
from scripts.personal_workstation.build_dashboard_state import build_dashboard_state  # noqa: E402
from scripts.personal_workstation.build_indexes import build_indexes  # noqa: E402
from scripts.personal_workstation.build_obsidian_views import build_obsidian_views  # noqa: E402
from scripts.personal_workstation.build_rag_manifest import build_rag_manifest  # noqa: E402
from scripts.personal_workstation.build_search_index import build_search_index  # noqa: E402
from scripts.personal_workstation.build_static_dashboard import build_static_dashboard  # noqa: E402
from scripts.personal_workstation.common import (  # noqa: E402
    WorkstationContext,
    ensure_directory_structure,
    frontmatter,
    make_context,
    safe_slug,
    stable_id,
    today_string,
    write_text_file,
)
from scripts.personal_workstation.normalize_metadata import normalize_metadata  # noqa: E402
from scripts.personal_workstation.write_codex_task_note import create_codex_task_note  # noqa: E402
from scripts.personal_workstation.write_daily_note import create_daily_note  # noqa: E402
from scripts.personal_workstation.write_knowledge_card import create_knowledge_card  # noqa: E402
from scripts.personal_workstation.write_project_status import create_project_status  # noqa: E402


def seed_core_notes(ctx: WorkstationContext, note_date: str):
    results = []
    domains = ["算法", "Agent", "项目", "工程能力"]
    results.append(
        write_text_file(
            ctx.target_root / "00_Home" / "Dashboard.md",
            frontmatter(
                {
                    "type": "home-dashboard",
                    "status": "active",
                    "source": "personal_workstation.init_workstation",
                    "preview": bool(ctx.config.get("preview_mode", True)),
                },
                ["workstation", "dashboard"],
            )
            + """# Personal AI Workstation

## 今日入口
- [[使用说明|每日使用说明]]
- [[AI_Workstation.canvas|可视化工作站地图]]
- [[../01_Daily/|每日工作流]]
- [[../00_Inbox/Inbox|Inbox]]
- [[../dashboard.html|静态 Dashboard]]

## 四大沉淀区
- [[../06_Learning/算法/|算法]]
- [[../06_Learning/Agent/|Agent]]
- [[../02_Projects/|项目]]
- [[../06_Learning/工程能力/|工程能力]]

## 进度与复盘
- [[../99_System/Indexes/Project_Index|项目进度表]]
- [[../99_System/Indexes/Learning_Index|学习进度表]]
- [[../99_System/Indexes/Document_Index|文档进度表]]
- [[../99_System/Indexes/Project_Log_Index|项目细节索引]]
- [[../05_Reviews/Daily/|每日复盘]]
- [[../05_Reviews/Weekly/|周复盘]]

## Obsidian 查询视图
- [[Dataview_Dashboard]]
- [[../99_System/Views/Projects_View|项目视图]]
- [[../99_System/Views/Learning_View|学习视图]]
- [[../99_System/Views/Documents_View|文档视图]]
- [[../99_System/Views/Project_Logs_View|项目日志视图]]

## 工作原则
- Local-first：默认写入本地 Obsidian vault。
- Obsidian-first：长期回看以 Markdown vault 为主。
- Audit-friendly：自动生成内容默认需要人工复核。
- Safe-by-default：不联网、不读 secret、不自动 git commit、不覆盖已有笔记。
""",
            overwrite=bool(ctx.config.get("allow_overwrite", False)),
        )
    )
    results.append(
        write_text_file(
            ctx.target_root / "00_Home" / "使用说明.md",
            frontmatter(
                {
                    "type": "workstation-manual",
                    "id": "workstation-manual",
                    "status": "active",
                    "source": "personal_workstation.init_workstation",
                    "preview": bool(ctx.config.get("preview_mode", True)),
                    "human_review_required": False,
                    "human_reviewed": True,
                    "created": note_date,
                    "updated": note_date,
                },
                ["manual", "workstation"],
            )
            + """# 个人 AI 工作站使用说明

## 每天的基本流程

1. 开始工作前，打开 [[Dashboard]] 或 [[AI_Workstation.canvas]]。
2. 把当天目标写到 `01_Daily/YYYY-MM-DD.md`。
3. 工作过程中按事情类型写入对应位置，不要都堆到 Daily Note。
4. 晚上运行 `closeout`，刷新每日汇总、复盘、进度表、Dashboard 和搜索。
5. 复盘时只看事实、产物、决策和下一步，不追求当天笔记一次写完美。

## 每日 AI Infra / AgentOps / LLMOps 学习自动化

- 每天优先检索最近 48 小时内的工程可用新内容，来源优先级是 OpenAI、Anthropic、Google、Microsoft、LangChain、vLLM、Ray、OpenTelemetry、OWASP、主流向量库、arXiv 工程论文、GitHub release。
- 只收录能落地到大模型应用开发、AgentOps、LLMOps、AI Infra，并且能服务简历项目、工作台或面试表达的内容。
- 如果当天没有合格新内容，就按 P0 fallback 队列学习：Agent Harness、MCP、A2A、AG-UI、主流 Agent SDK、LangGraph、Context Engineering、Tool Design、RAG 2.0、Agent/RAG Evaluation、LLM Observability、Inference Serving、Agent Security、Structured Output、Multimodal Agent Pipeline。
- 如果当前主线是“多 Agent 协作工作台”，没有新内容时优先讲工作台模块 fallback 队列，并跳过已经讲过的 topic：Memory Architecture、Memory Policy、Memory Namespace、Model Gateway、Model Routing、Tool Gateway、Agent Registry、Concurrent Execution、Backpressure、Durable Workflow、Idempotency、Event Bus、Shared State、Artifact Store、Run Replay、Config Registry、Policy Engine、Approval Center、Sandbox Pool、Cost Metering。
- 产物固定落在 `06_Learning/Agent/前沿研究/`，并包含：主题一句话结论、核心架构、关键模块、工程落地、面试追问、30-60 分钟 mini demo、如何写进项目或简历表达。
- 工作台模块还会额外包含：这个模块解决工作台里的什么问题、它在多 Agent 架构中的位置、核心数据结构或表设计、核心 API 设计、最小 demo、如何写进我的简历项目。

## 不同事情写在哪里

| 你正在做的事 | 写入位置 | 推荐命令 |
| --- | --- | --- |
| 临时想法、突然冒出的任务 | `00_Inbox/Inbox.md` | `workstation.py inbox --title "标题" --body "内容"` |
| 每日计划、当天复盘 | `01_Daily/YYYY-MM-DD.md` | `workstation.py daily` / `workstation.py closeout` |
| 学算法、刷题、题解复盘 | `06_Learning/算法/` | `workstation.py learning --area 算法 --topic "主题"` |
| 学 Agent、提示词、多智能体流程 | `06_Learning/Agent/` | `workstation.py learning --area Agent --topic "主题"` |
| AI Infra、AgentOps、LLMOps 前沿研究与 fallback 学习 | `06_Learning/Agent/前沿研究/` | `workstation.py agent-research --input-json result.json` / `workstation.py agent-research` |
| 学项目相关知识、项目方法论 | `06_Learning/项目/` | `workstation.py learning --area 项目 --topic "主题"` |
| 学工程能力、架构、调试、测试、部署 | `06_Learning/工程能力/` | `workstation.py learning --area 工程能力 --topic "主题"` |
| 项目推进、关键上下文、决策、风险 | `02_Projects/{项目名}/Logs/` | `workstation.py project-log --project "项目名" --title "标题"` |
| Codex 帮你完成的一次任务 | `03_Codex_Tasks/` | `workstation.py codex-task --project "项目名" --task "任务名"` |
| 写文档、报告、说明书、方案 | `08_Artifacts/Document_Logs/` | `workstation.py document --title "文档标题" --project "项目名"` |
| 已经稳定、值得长期复用的知识 | `04_Knowledge/{算法/Agent/项目/工程能力}/` | `workstation.py knowledge --domain Agent --topic "主题"` |
| 每日、每周、项目复盘 | `05_Reviews/` | `workstation.py review --type daily` |

## 怎么判断写学习还是知识卡片

- 还在探索、练习、试错：写到 `06_Learning/`。
- 已经验证过、以后会复用：整理到 `04_Knowledge/`。
- 和某个具体项目有关：优先写到 `02_Projects/{项目名}/Logs/`。
- 只是一个念头：先扔到 `00_Inbox/Inbox.md`。

## 在哪里看进度

| 想看的东西 | 看哪里 |
| --- | --- |
| 总入口 | [[Dashboard]] |
| 可视化地图 | [[AI_Workstation.canvas]] |
| 今日机器汇总 | `99_System/Daily_Sync/YYYY-MM-DD.md` |
| 项目进度 | `99_System/Indexes/Project_Index.md` |
| 学习进度 | `99_System/Indexes/Learning_Index.md` |
| Agent 前沿研究 | `06_Learning/Agent/前沿研究/` |
| 文档进度 | `99_System/Indexes/Document_Index.md` |
| 项目细节 | `99_System/Indexes/Project_Log_Index.md` |
| 待审核内容 | `99_System/Indexes/Pending_Review_Index.md` |
| 每日复盘 | `05_Reviews/Daily/` |
| 周复盘 | `05_Reviews/Weekly/` |
| 本地静态 Dashboard | `dashboard.html` |
| 本地搜索 | `99_System/Search/search.html` |

## 推荐收口命令

```powershell
python -B scripts\\personal_workstation\\workstation.py --config configs\\personal_workstation.local.json closeout
```

它会刷新：

- Daily Sync 机器汇总
- 每日复盘
- 进度索引
- Dataview 视图
- Canvas
- 静态 Dashboard
- 本地搜索

## 核心原则

- Daily Note 只做当天入口，不承载所有细节。
- 项目事实写项目日志，学习过程写学习目录，稳定结论写知识卡片。
- 自动生成内容默认需要人工复核。
- 当前阶段不做真实 embedding，不写向量库；先保证 Obsidian 沉淀流程稳定。
""",
            overwrite=bool(ctx.config.get("allow_overwrite", False)),
        )
    )
    for domain in domains:
        results.append(
            write_text_file(
                ctx.target_root / "06_Learning" / domain / "Index.md",
                frontmatter(
                    {
                        "type": "learning-area",
                        "id": stable_id("learning-area", domain),
                        "area": domain,
                        "status": "active",
                        "source": "personal_workstation.init_workstation",
                        "preview": bool(ctx.config.get("preview_mode", True)),
                        "human_review_required": False,
                        "human_reviewed": True,
                        "created": note_date,
                        "updated": note_date,
                    },
                    ["learning", "area", "workstation"],
                )
                + f"""# {domain}

## 入口
- 学习记录放在本目录。
- 稳定结论沉淀到 `04_Knowledge/{domain}/`。
- 当天学习会通过 `closeout` 汇总到 Daily Note。

## 当前关注
- [ ] 补充本阶段最重要的学习目标。
- [ ] 补充正在跟进的资料、课程、项目或练习。
""",
                overwrite=bool(ctx.config.get("allow_overwrite", False)),
            )
        )
        results.append(
            write_text_file(
                ctx.target_root / "04_Knowledge" / domain / "Index.md",
                frontmatter(
                    {
                        "type": "knowledge-area",
                        "id": stable_id("knowledge-area", domain),
                        "domain": domain,
                        "status": "active",
                        "source": "personal_workstation.init_workstation",
                        "preview": bool(ctx.config.get("preview_mode", True)),
                        "human_review_required": False,
                        "human_reviewed": True,
                        "created": note_date,
                        "updated": note_date,
                    },
                    ["knowledge", "area", "workstation"],
                )
                + f"""# {domain} 知识沉淀

## 用法
- 这里只放经过复盘后相对稳定的知识卡片。
- 日常过程先写到 `06_Learning/{domain}/` 或项目日志。
- 需要人工确认的内容保持 `human_reviewed=false`。
""",
                overwrite=bool(ctx.config.get("allow_overwrite", False)),
            )
        )
    results.append(
        write_text_file(
            ctx.target_root / "00_Inbox" / "Inbox.md",
            frontmatter(
                {
                    "type": "inbox",
                    "status": "active",
                    "source": "personal_workstation.init_workstation",
                    "human_review_required": True,
                },
                ["inbox", "workstation"],
            )
            + """# Inbox

## 临时想法
- 待补充。

## 待整理知识点
- 待补充。

## 待复盘问题
- 待补充。

## 待问 Codex 的问题
- 待补充。

## 待做任务
- 待补充。

## 待审核产物
- 待补充。
""",
            overwrite=bool(ctx.config.get("allow_overwrite", False)),
        )
    )
    results.append(
        write_text_file(
            ctx.target_root / "01_Daily" / "Index.md",
            frontmatter(
                {
                    "type": "daily-index",
                    "id": "daily-index",
                    "status": "active",
                    "source": "personal_workstation.init_workstation",
                    "preview": bool(ctx.config.get("preview_mode", True)),
                    "human_review_required": False,
                    "human_reviewed": True,
                    "created": note_date,
                    "updated": note_date,
                },
                ["daily", "index", "workstation"],
            )
            + """# 每日工作流

## 怎么用
- 每天开始先看当天 Daily Note。
- 工作过程中把学习、项目细节、文档写作分别落到对应目录。
- 每天结束运行 `closeout`，自动刷新汇总、索引、复盘和 dashboard。

## 入口
- [[../00_Home/Dashboard|工作站首页]]
- [[../99_System/Indexes/Learning_Index|学习进度表]]
- [[../99_System/Indexes/Project_Index|项目进度表]]
- [[../99_System/Indexes/Document_Index|文档进度表]]
""",
            overwrite=bool(ctx.config.get("allow_overwrite", False)),
        )
    )
    results.append(
        write_text_file(
            ctx.target_root / "08_Artifacts" / "Artifact_Index.md",
            frontmatter(
                {
                    "type": "artifact-index",
                    "status": "active",
                    "source": "personal_workstation.init_workstation",
                    "updated": note_date,
                },
                ["artifacts", "workstation"],
            )
            + """# Artifact Index

| Artifact | Path | Review |
| --- | --- | --- |
| Dashboard | `dashboard.html` | required |
| State JSON | `workstation_state.json` | required |
| Canvas | `00_Home/AI_Workstation.canvas` | required |
| Document Logs | `08_Artifacts/Document_Logs/` | required |
""",
            overwrite=bool(ctx.config.get("allow_overwrite", False)),
        )
    )
    results.append(
        write_text_file(
            ctx.target_root / "99_System" / "Config.md",
            frontmatter(
                {
                    "type": "system-config",
                    "status": "active",
                    "source": "personal_workstation.init_workstation",
                    "preview": bool(ctx.config.get("preview_mode", True)),
                },
                ["system", "workstation"],
            )
            + f"""# Workstation Config

## 当前模式
- preview_mode: {str(ctx.config.get("preview_mode", True)).lower()}
- target_root: `{ctx.target_root}`
- allow_overwrite: {str(ctx.config.get("allow_overwrite", False)).lower()}
- safe_append_only: {str(ctx.config.get("safe_append_only", True)).lower()}

## 安全边界
- 不读取 secret。
- 不联网。
- 不自动 git commit。
- 不删除用户文件。
- 默认不覆盖已有 Obsidian 笔记。
""",
            overwrite=bool(ctx.config.get("allow_overwrite", False)),
        )
    )
    results.append(
        write_text_file(
            ctx.target_root / "99_System" / "Templates" / "Daily_Note_Template.md",
            """# Daily Note Template

## 今日目标
- [ ]

## 今日复盘
-

## 今日执行记录
-
""",
            overwrite=bool(ctx.config.get("allow_overwrite", False)),
        )
    )
    results.append(
        write_text_file(
            ctx.target_root / "99_System" / "Templates" / "Project_Template.md",
            """# Project Template

## 项目定位

## 长期目标

## 当前状态

## 阶段目标

## 风险

## 产物
""",
            overwrite=bool(ctx.config.get("allow_overwrite", False)),
        )
    )
    results.append(
        write_text_file(
            ctx.target_root / "99_System" / "Templates" / "Codex_Task_Template.md",
            """# Codex Task Template

## 任务目标

## 输入材料

## 实际完成内容

## Changed Files

## 验证结果

## 执行边界
""",
            overwrite=bool(ctx.config.get("allow_overwrite", False)),
        )
    )
    results.append(
        write_text_file(
            ctx.target_root / "99_System" / "Templates" / "Knowledge_Card_Template.md",
            """# Knowledge Card Template

## 一句话解释

## 适用场景

## 核心概念

## 常见误区

## 相关链接
""",
            overwrite=bool(ctx.config.get("allow_overwrite", False)),
        )
    )
    results.append(
        write_text_file(
            ctx.target_root / "99_System" / "Templates" / "Learning_Note_Template.md",
            """# Learning Note Template

## 学习目标

## 输入材料

## 关键概念

## 实践/练习

## 疑问

## 可沉淀知识卡片

## 今日结论

## 下一步
""",
            overwrite=bool(ctx.config.get("allow_overwrite", False)),
        )
    )
    results.append(
        write_text_file(
            ctx.target_root / "99_System" / "Templates" / "Document_Log_Template.md",
            """# Document Log Template

## 文档目标

## 目标读者

## 结构大纲

## 已完成内容

## 关联项目

## 关联产物

## 待完善

## 审核状态
""",
            overwrite=bool(ctx.config.get("allow_overwrite", False)),
        )
    )
    results.append(
        write_text_file(
            ctx.target_root / "99_System" / "Templates" / "Project_Log_Template.md",
            """# Project Log Template

## 发生了什么

## 关键决策

## 证据/上下文

## 影响范围

## 下一步

## 审核状态
""",
            overwrite=bool(ctx.config.get("allow_overwrite", False)),
        )
    )
    results.append(
        write_text_file(
            ctx.target_root / "99_System" / "Templates" / "Review_Template.md",
            """# Review Template

## 本周期目标

## 已完成

## 关键证据

## 风险

## 下一步
""",
            overwrite=bool(ctx.config.get("allow_overwrite", False)),
        )
    )
    results.append(
        write_text_file(
            ctx.target_root / "99_System" / "Schemas" / "workstation_state.schema.json",
            """{
  "type": "object",
  "required": ["generated_at", "preview_mode", "today", "counts", "active_projects", "recent_codex_tasks", "audit"]
}
""",
            overwrite=bool(ctx.config.get("allow_overwrite", False)),
        )
    )
    return results


def initialize_workstation(
    ctx: WorkstationContext,
    note_date: str | None = None,
    project_name: str = "Personal AI Workstation",
    task_title: str = "Bootstrap MVP",
    topic: str = "个人 AI 工作站的本地优先知识沉淀",
):
    note_date = note_date or today_string(ctx)
    ensure_directory_structure(ctx)
    results = []
    results.extend(seed_core_notes(ctx, note_date))
    results.append(create_daily_note(ctx, note_date))
    results.extend(create_project_status(ctx, project_name, note_date))
    task_path = ctx.target_root / str(ctx.config["codex_tasks_dir"]) / f"{note_date}_{safe_slug(project_name)}_{safe_slug(task_title)}.md"
    if not task_path.exists():
        results.append(
            create_codex_task_note(
                ctx,
                note_date,
                project_name,
                task_title,
                "生成个人 AI 工作站第一阶段 MVP 骨架，并保持 preview、安全、可验证。",
            )
        )
    knowledge_path = ctx.target_root / str(ctx.config["knowledge_dir"]) / "Agent" / f"{safe_slug(topic)}.md"
    if not knowledge_path.exists():
        results.append(create_knowledge_card(ctx, topic, "Agent"))
    results.extend(normalize_metadata(ctx))
    if ctx.config.get("generate_canvas", True):
        results.append(build_canvas(ctx))
    results.extend(build_indexes(ctx))
    results.extend(build_obsidian_views(ctx))
    results.extend(build_rag_manifest(ctx))
    results.extend(build_search_index(ctx))
    state_result, state = build_dashboard_state(ctx, note_date)
    results.append(state_result)
    if ctx.config.get("generate_dashboard", True):
        results.append(build_static_dashboard(ctx, state))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the Personal AI Workstation MVP.")
    parser.add_argument("--config", default=None)
    parser.add_argument("--date", default=None)
    parser.add_argument("--project", default="Personal AI Workstation")
    parser.add_argument("--task", default="Bootstrap MVP")
    parser.add_argument("--topic", default="个人 AI 工作站的本地优先知识沉淀")
    args = parser.parse_args()
    ctx = make_context(args.config)
    results = initialize_workstation(ctx, args.date, args.project, args.task, args.topic)
    print(f"target_root: {ctx.target_root}")
    for result in results:
        print(f"{result.action}: {result.path}")


if __name__ == "__main__":
    main()
