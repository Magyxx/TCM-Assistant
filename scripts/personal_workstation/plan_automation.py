from __future__ import annotations

import argparse
import re
import sys
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.personal_workstation.common import (  # noqa: E402
    WorkstationContext,
    WriteResult,
    configured_path,
    frontmatter,
    make_context,
    now_iso,
    stable_id,
    today_string,
    upsert_marked_section,
    write_text_file,
)
from scripts.personal_workstation.sync_daily import collect_learning_notes, sync_daily  # noqa: E402
from scripts.personal_workstation.write_daily_note import create_daily_note  # noqa: E402


XIAOHONGSHU_PAUSED = True
EXAMS_PAUSED = True
ALGORITHM_DAILY_TARGET_POINTS = 5
ALGORITHM_SCORING_RULE = "easy=1，medium=2，hard=3"

MODULES = {
    "A": "简历项目整理与工程化",
    "B": "多 Agent 协作工作台推进",
    "C": "AI 前沿 / 热门架构学习",
    "D": "长期技术栈补充",
    "E": "算法 Hot100",
    "F": "内容发布（暂停）",
    "G": "考试复习与缓冲",
}

EXAMS = [date(2026, 6, 18), date(2026, 6, 29)]


PHASES: list[dict[str, Any]] = [
    {
        "start": date(2026, 6, 13),
        "end": date(2026, 6, 19),
        "positioning": "考试周 + 简历项目启动周",
        "goals": [
            "完成第一轮简历项目盘点，明确 2-3 个主项目的包装方向。",
            "为 6 月 18 日考试留出复习时间。",
            "小红书计划暂停，不纳入本周交付。",
            "保持每日 AI 前沿 / 热门架构学习，但不做过重 demo。",
            "保持算法 Hot100 连续性。",
        ],
        "priorities": {
            "P0": "简历项目整理与工程化；考试前 3 天自动切换为考试复习 P0。",
            "P1": "考试复习与缓冲。",
            "P2": "算法 Hot100 最低连续性。",
            "P3": "AI 前沿 / 热门架构学习，必须能服务简历、工作台、面试或小红书。",
            "P4": "长期技术栈补充与小红书保底发布。",
        },
        "non_negotiable": [
            "6 月 18 日考试复习。",
            "简历项目主线。",
            "算法 Hot100 最低连续性。",
            "每日复盘。",
        ],
        "cuttable": [
            "复杂 demo。",
            "非必要的新技术深挖。",
            "过长的小红书选题研究。",
            "多 Agent 工作台的重型代码开发。",
        ],
        "modules": {
            "A": {
                "goal": "完成第一轮简历项目盘点，并把 toB 多源订单系统、字节短剧 / 多 Agent pipeline 作为主包装候选。",
                "deliverables": [
                    "可写进简历的项目清单。",
                    "2-3 个主项目筛选结果。",
                    "每个主项目的背景、技术栈、架构、职责、难点、方案、量化结果、面试追问。",
                    "toB 多源订单智能采集与结构化处理系统的简历初稿。",
                    "字节短剧 / 多 Agent pipeline 项目的第一版包装思路。",
                ],
                "minimum": "至少完成项目清单、主项目筛选和 1 个主项目初稿。",
                "stretch": "补齐 2 个主项目的 STAR 讲述和面试追问。",
            },
            "B": {
                "goal": "只做设计和模块拆分，不做重型开发。",
                "deliverables": [
                    "工作台总体架构草图。",
                    "核心模块列表。",
                    "MVP 功能范围。",
                    "数据表初稿。",
                    "Agent Runtime / Memory / Gateway / Event / Artifact / Approval 模块边界。",
                ],
                "minimum": "形成文字版架构边界和 MVP 范围。",
                "stretch": "补一个模块间数据流草图。",
            },
            "C": {
                "goal": "每天 1 个工程主题，考试前两天只做轻量笔记。",
                "minimum": "每天输出 5-8 条可复用笔记。",
                "reuse": "必须映射到简历项目、多 Agent 工作台、小红书或面试表达之一。",
            },
            "D": {
                "goal": "补齐 Python 工程化和后端 infra 基础。",
                "minimum": "至少 3 个技术栈学习笔记和 1 个可复用 demo / 伪代码设计。",
                "stretch": "把 demo 绑定到多 Agent 工作台模块。",
            },
            "E": {
                "goal": "本周 10-12 道，考试前可降到每天 1 道。",
                "minimum": "不能连续两天为 0；周内整理错题和模板。",
                "stretch": "按题型沉淀模板代码。",
            },
            "F": {
                "goal": "本周至少 2 篇，理想 3 篇。",
                "minimum": "每篇包含标题、3 段正文、1 个类比、1 张配图提示词、3 个标签。",
                "stretch": "从每日学习笔记直接复用，减少额外打磨。",
            },
            "G": {
                "goal": "6 月 18 日考试前自动提高复习权重。",
                "minimum": "明确考试范围，整理重点知识点，完成至少一轮核心内容复习。",
                "stretch": "考前一天只做复盘、错题和记忆型内容。",
            },
        },
        "frontier_topics": [
            "Agent Harness / Agent Loop",
            "MCP",
            "LangGraph Stateful Runtime",
            "Context Engineering",
            "Agent Memory Architecture",
            "Model Gateway",
            "Tool Gateway",
        ],
        "tech_stack": [
            ("Python typing / Pydantic", "API schema"),
            ("FastAPI 基础接口设计", "API"),
            ("PostgreSQL 表设计", "数据库"),
            ("Redis session / task state", "状态管理"),
            ("asyncio 并发基础", "并发"),
        ],
        "resume_daily": [
            "列出所有可写进简历的项目，并按 AI Infra / AgentOps 相关度排序。",
            "筛选 2-3 个主项目，确定 toB 多源订单系统和字节短剧 / 多 Agent pipeline 的包装角度。",
            "写 toB 多源订单系统的项目背景、技术栈和系统架构。",
            "补 toB 项目的职责、难点、解决方案和量化指标。",
            "写字节短剧 / 多 Agent pipeline 的第一版包装思路。",
            "把两个主项目整理成可面试追问的问题清单。",
        ],
        "agent_daily": [
            "列工作台核心模块和 MVP 边界。",
            "拆 Agent Runtime / Memory / Gateway / Event / Artifact / Approval 的模块职责。",
            "写 Run / Task / Artifact 的数据表初稿。",
            "画文字版数据流：planner -> worker -> aggregator -> artifact。",
        ],
        "xhs_topics": ["MCP 是什么", "Agent Harness 是什么", "多 Agent 工作台为什么需要记忆和网关"],
        "algorithm_target": "10-12 道",
        "algorithm_focus": ["哈希", "双指针", "滑动窗口", "二叉树"],
    },
    {
        "start": date(2026, 6, 20),
        "end": date(2026, 6, 28),
        "positioning": "高强度项目冲刺周 + 6 月 29 日考试预备周",
        "goals": [
            "把简历项目从材料整理推进到可写进简历的完整版本。",
            "多 Agent 协作工作台完成 MVP 设计，并开始实现核心骨架。",
            "6 月 25 日起逐步提高 6 月 29 日考试复习权重。",
            "保持算法、小红书、前沿学习不断档。",
            "把每日学习内容尽量反哺项目和简历。",
        ],
        "priorities": {
            "P0": "简历项目最终包装。",
            "P1": "6 月 29 日考试复习；6 月 25 日起加权。",
            "P2": "多 Agent 工作台 MVP 设计和最小骨架。",
            "P3": "算法 Hot100 最低连续性。",
            "P4": "前沿学习、技术栈补充、小红书保底发布。",
        },
        "non_negotiable": [
            "简历项目最终包装。",
            "6 月 29 日考试复习。",
            "多 Agent 工作台 MVP 设计。",
            "算法最低连续性。",
            "每日复盘与动态调整。",
        ],
        "cuttable": [
            "小红书过度打磨。",
            "非核心技术栈扩展。",
            "与 AI Infra / AgentOps 无关的泛 AI 新闻。",
            "超出 MVP 的工作台功能。",
        ],
        "modules": {
            "A": {
                "goal": "完成 toB 多源订单系统和字节短剧 / 多 Agent pipeline 的完整简历版本。",
                "deliverables": [
                    "toB 多源订单系统完整简历版本。",
                    "字节短剧 / 互动内容 / 多 Agent pipeline 完整简历版本。",
                    "每个项目的 bullet、STAR 讲述、架构描述、难点、量化指标和追问清单。",
                    "AI Infra / AgentOps 方向简历关键词。",
                ],
                "minimum": "至少完成两个主项目的简历 bullet 和 STAR 初稿。",
                "stretch": "补齐岗位关键词匹配表。",
            },
            "B": {
                "goal": "进入 MVP 骨架实现。",
                "deliverables": [
                    "项目 README 初稿。",
                    "架构图文字版。",
                    "核心数据表设计。",
                    "planner -> researcher / coder / reviewer -> aggregator 最小 demo。",
                ],
                "minimum": "完成 README、架构说明和核心数据表。",
                "stretch": "跑通 1 个最小 demo。",
            },
            "C": {
                "goal": "每天 1 个主题，6 月 27-28 日降为轻量笔记。",
                "minimum": "每天输出短笔记，必须服务项目或简历。",
                "reuse": "反哺工作台模块设计、小红书选题和面试表达。",
            },
            "D": {
                "goal": "技术栈学习必须和多 Agent 工作台绑定。",
                "minimum": "至少 4 次 1 小时学习，至少 2 个小 demo 或代码骨架。",
                "stretch": "把技术栈产出并入工作台 README 或架构说明。",
            },
            "E": {
                "goal": "本周 12-15 道，6 月 27-28 日可降到每天 1 道。",
                "minimum": "保持不断档并整理错题复盘。",
                "stretch": "覆盖哈希、双指针、滑动窗口、二叉树、动态规划入门。",
            },
            "F": {
                "goal": "本周至少 3 篇。",
                "minimum": "必须从学习笔记复用，不重新开新坑。",
                "stretch": "形成一组多 Agent 工作台科普系列。",
            },
            "G": {
                "goal": "6 月 25 日起进入考试复习加权模式。",
                "minimum": "完成考试范围梳理、一轮重点复习、错题 / 重点 / 记忆点整理。",
                "stretch": "6 月 28 日只做复习、轻量算法和总结。",
            },
        },
        "frontier_topics": [
            "Agent Memory Architecture",
            "Memory Write / Read / Forget Policy",
            "Memory Scope / Namespace Design",
            "Model Gateway / LLM Gateway",
            "Model Routing Strategy",
            "Tool Gateway / Capability Gateway",
            "Agent Registry / Capability Registry",
            "Concurrent Agent Execution",
            "Queue / Backpressure / Rate Limit",
            "Durable Workflow",
        ],
        "tech_stack": [
            ("FastAPI 项目结构", "API"),
            ("PostgreSQL 表设计与索引", "数据库"),
            ("Redis 缓存与状态管理", "状态管理"),
            ("asyncio / 并发任务", "并发"),
            ("Celery / RQ / 任务队列基础", "任务队列"),
            ("Docker Compose", "deployment"),
        ],
        "resume_daily": [
            "完成 toB 多源订单系统简历 bullet 初稿。",
            "完成 toB 项目的 STAR 面试讲述。",
            "完成字节短剧 / 多 Agent pipeline 简历 bullet 初稿。",
            "完成字节短剧项目的架构描述和技术难点。",
            "整理 AI Infra / AgentOps 岗位关键词匹配表。",
            "把两个主项目合并成一版可投递简历项目经历。",
        ],
        "agent_daily": [
            "写 Agent Registry 和 Run / Task 数据结构。",
            "设计 Memory Namespace。",
            "设计 Model Gateway 统一调用层。",
            "设计 Tool Gateway 权限检查层。",
            "设计 Event Stream 日志结构。",
            "设计 Artifact Store 结构。",
            "实现最小 planner / worker / aggregator demo。",
        ],
        "xhs_topics": [
            "多 Agent 为什么需要记忆系统",
            "Model Gateway 是什么",
            "Tool Gateway 和 MCP 的区别",
            "多 Agent 并发为什么会带来系统雪崩",
        ],
        "algorithm_target": "12-15 道",
        "algorithm_focus": ["哈希", "双指针", "滑动窗口", "二叉树", "动态规划入门"],
    },
    {
        "start": date(2026, 6, 29),
        "end": date(2026, 7, 5),
        "positioning": "考试日 + 实习低强度过渡周",
        "goals": [
            "6 月 29 日完成考试。",
            "考试后切换为公司实习期间的低强度维护节奏。",
            "保持算法、AI 前沿、小红书不断档，但降低每日负担。",
            "简历项目进入打磨和投递准备阶段。",
            "多 Agent 工作台进入小步迭代。",
        ],
        "priorities": {
            "P0": "考试当天完成考试；考试后简历项目打磨。",
            "P1": "每日复盘和低强度维护节奏。",
            "P2": "算法最低频率。",
            "P3": "轻量 AI 前沿学习。",
            "P4": "小红书和技术栈维护。",
        },
        "non_negotiable": [
            "考试。",
            "每日复盘。",
            "简历项目打磨。",
            "算法最低频率。",
            "每日轻量 AI 前沿学习。",
        ],
        "cuttable": [
            "大规模新功能开发。",
            "重型技术栈 demo。",
            "复杂小红书内容。",
            "超过 1 小时的非必要探索。",
        ],
        "modules": {
            "A": {
                "goal": "完成一版可投递简历和项目经历最终版。",
                "deliverables": [
                    "可投递简历。",
                    "项目经历最终版。",
                    "每个项目 2 分钟讲述版本。",
                    "每个项目 8-10 个面试追问。",
                    "AI Infra / AgentOps / LLMOps 岗位关键词匹配表。",
                ],
                "minimum": "可投递简历 + 2 分钟项目讲述。",
                "stretch": "补齐追问清单和关键词匹配。",
            },
            "B": {
                "goal": "小步稳定迭代，不追求大规模推进。",
                "deliverables": [
                    "README 优化。",
                    "架构说明。",
                    "数据结构稳定。",
                    "一个可运行的最小 demo。",
                    "后续 backlog。",
                ],
                "minimum": "能说清楚工作台解决什么问题，以及它和普通聊天机器人 / 多 Agent demo 的区别。",
                "stretch": "补一个可运行最小 demo。",
            },
            "C": {
                "goal": "每天轻量学习一个主题，30-45 分钟。",
                "minimum": "短笔记不断档。",
                "reuse": "输出面向项目、面试或小红书。",
            },
            "D": {
                "goal": "维护型学习，30-60 分钟。",
                "minimum": "至少 3 次技术栈学习，至少 1 个和工作台相关的小改动。",
                "stretch": "把小改动并入 README 或 demo。",
            },
            "E": {
                "goal": "本周 7-10 道。",
                "minimum": "每天可降为 1 道，周末错题复盘。",
                "stretch": "补齐高频模板。",
            },
            "F": {
                "goal": "本周至少 2 篇。",
                "minimum": "低成本选题，不追求爆款。",
                "stretch": "复用工作台迭代内容。",
            },
            "G": {
                "goal": "6 月 29 日考试当天不安排重型开发，考后 1-2 天恢复节奏。",
                "minimum": "完成考试，逐步进入维护模式。",
                "stretch": "形成实习期维护节奏模板。",
            },
        },
        "frontier_topics": [
            "Artifact Store",
            "Run Replay / Time-travel Debugging",
            "Prompt / Agent Config Registry",
            "Policy Engine / Permission as Code",
            "Human Task Queue / Approval Center",
            "Sandbox Execution Pool",
            "Cost Metering / Budget Control",
        ],
        "tech_stack": [
            ("Docker Compose", "deployment"),
            ("FastAPI 项目结构", "API"),
            ("PostgreSQL + Redis 实战", "数据库 / 状态管理"),
            ("任务队列", "任务队列"),
            ("OpenTelemetry 基础", "tracing"),
        ],
        "resume_daily": [
            "整理一版可投递简历。",
            "打磨项目经历最终版。",
            "准备每个项目的 2 分钟讲述。",
            "准备项目面试追问。",
            "整理岗位关键词匹配表。",
        ],
        "agent_daily": [
            "优化 README。",
            "补架构说明。",
            "稳定核心数据结构。",
            "整理最小 demo 和 backlog。",
        ],
        "xhs_topics": [
            "为什么多 Agent 工作台需要 artifact",
            "Agent 运行失败后为什么要能回放",
            "AI 应用为什么要做成本控制",
        ],
        "algorithm_target": "7-10 道",
        "algorithm_focus": ["错题复盘", "哈希", "双指针", "二叉树"],
    },
]


def parse_day(ctx: WorkstationContext, value: str | None = None) -> date:
    return date.fromisoformat(value or today_string(ctx))


def format_day(day: date) -> str:
    return day.strftime("%Y.%m.%d")


def md_list(items: list[str], *, checkbox: bool = False) -> str:
    marker = "- [ ]" if checkbox else "-"
    return "\n".join(f"{marker} {item}" for item in items)


def phase_for(day: date) -> dict[str, Any]:
    for phase in PHASES:
        if phase["start"] <= day <= phase["end"]:
            return apply_content_policy(deepcopy(phase))

    week_start = day - timedelta(days=day.weekday())
    phase = deepcopy(PHASES[-1])
    phase["start"] = week_start
    phase["end"] = week_start + timedelta(days=6)
    phase["positioning"] = "实习维护周 + 求职项目打磨周"
    phase["goals"] = [
        "保持简历项目持续打磨。",
        "保持算法、AI 前沿和技术栈最低频率。",
        "多 Agent 工作台小步迭代。",
        "把学习内容继续反哺面试表达和小红书。",
    ]
    return apply_content_policy(phase)


def apply_content_policy(phase: dict[str, Any]) -> dict[str, Any]:
    if EXAMS_PAUSED:
        phase["positioning"] = phase["positioning"].replace("考试周 + ", "").replace(" + 6 月 29 日考试预备周", "")
        phase["goals"] = [goal for goal in phase["goals"] if "考试" not in goal and "复习" not in goal]
        phase["goals"].append("考试暂时结束，不纳入每日任务加权。")
        phase["priorities"] = {
            level: text.replace("；考试前 3 天自动切换为考试复习 P0", "")
            .replace("考试复习与缓冲。", "缓冲与复盘。")
            .replace("6 月 29 日考试复习；6 月 25 日起加权。", "缓冲与复盘。")
            .replace("考试当天完成考试；考试后简历项目打磨。", "简历项目打磨。")
            for level, text in phase["priorities"].items()
        }
        phase["non_negotiable"] = [item for item in phase["non_negotiable"] if "考试" not in item]
        modules = phase["modules"]
        modules["C"]["goal"] = modules["C"]["goal"].replace("，考试前两天只做轻量笔记", "")
        modules["E"]["goal"] = f"每天至少 {ALGORITHM_DAILY_TARGET_POINTS} 分，按难度计分。"
        modules["E"]["minimum"] = (
            f"每日最低 {ALGORITHM_DAILY_TARGET_POINTS} 分（{ALGORITHM_SCORING_RULE}）；"
            "不能连续两天低于目标；记录题型、错因和模板。"
        )
        modules["G"] = {
            "goal": "暂停：考试暂时结束，不生成复习任务。",
            "minimum": "暂停期间不安排考试 P0 / P1，只保留必要缓冲。",
            "stretch": "无。",
        }
        phase["algorithm_target"] = f"每日 {ALGORITHM_DAILY_TARGET_POINTS} 分"

    if not XIAOHONGSHU_PAUSED:
        return phase

    phase["goals"] = [
        goal
        for goal in phase["goals"]
        if "小红书" not in goal
    ]
    phase["goals"].append("小红书计划暂停，不纳入每日任务和本周交付。")

    phase["priorities"] = {
        level: text.replace("与小红书保底发布", "")
        .replace("、小红书保底发布", "")
        .replace("小红书和技术栈维护", "技术栈维护")
        .replace("、小红书", "")
        for level, text in phase["priorities"].items()
    }
    phase["non_negotiable"] = [item for item in phase["non_negotiable"] if "小红书" not in item]
    phase["cuttable"] = [item for item in phase["cuttable"] if "小红书" not in item]
    phase["cuttable"].append("小红书发布、草稿和选题打磨。")

    modules = phase["modules"]
    modules["C"]["reuse"] = (
        modules["C"]["reuse"]
        .replace("、小红书", "")
        .replace("小红书选题和", "")
        .replace("或小红书", "")
    )
    modules["F"] = {
        "goal": "暂停：暂不安排发布、草稿和选题，只保留已有素材。",
        "minimum": "暂停期间不生成每日发布任务。",
        "stretch": "无。",
    }
    phase["xhs_topics"] = []
    return phase


def weekly_plan_path(ctx: WorkstationContext, phase: dict[str, Any]) -> Path:
    name = f"{phase['start'].isoformat()}_{phase['end'].isoformat()}_Plan.md"
    return configured_path(ctx, "reviews_dir") / "Weekly" / name


def render_weekly_plan(ctx: WorkstationContext, phase: dict[str, Any]) -> str:
    period = f"{format_day(phase['start'])} - {format_day(phase['end'])}"
    modules = phase["modules"]
    front = frontmatter(
        {
            "type": "weekly-plan",
            "id": stable_id("weekly-plan", period),
            "period": period,
            "plan_start": phase["start"].isoformat(),
            "plan_end": phase["end"].isoformat(),
            "status": "active",
            "source": "personal_workstation.plan_automation",
            "preview": bool(ctx.config.get("preview_mode", True)),
            "human_review_required": True,
            "human_reviewed": False,
            "created": phase["start"].isoformat(),
            "updated": now_iso(ctx),
        },
        ["planning", "weekly", "job-search", "learning"],
    )

    lines = [
        f"# 本周计划：{period}",
        "",
        "## 1. 本周定位",
        phase["positioning"],
        "",
        "## 2. 本周主目标",
        md_list(phase["goals"][:5]),
        "",
        "## 3. 本周优先级",
    ]
    lines.extend(f"- {level}：{text}" for level, text in phase["priorities"].items())
    lines.extend(["", "## 4. 本周模块计划", ""])

    for key, title in MODULES.items():
        module = modules[key]
        lines.extend(
            [
                f"### {key}. {title}",
                f"- 本周目标：{module['goal']}",
            ]
        )
        if "deliverables" in module:
            lines.append("- 本周交付物：")
            lines.extend(f"  - {item}" for item in module["deliverables"])
        if key == "C":
            lines.append("- 本周主题池：")
            lines.extend(f"  - {item}" for item in phase["frontier_topics"])
            lines.append(f"- 每日最低产出：{module['minimum']}")
            lines.append(f"- 如何复用到项目 / 面试：{module['reuse']}")
        elif key == "D":
            lines.append("- 本周技术栈：")
            lines.extend(f"  - {topic} -> {feature}" for topic, feature in phase["tech_stack"])
            lines.append(f"- 对应功能：{', '.join(sorted({feature for _, feature in phase['tech_stack']}))}")
            lines.append(f"- 最低 demo / 代码产出：{module['minimum']}")
        elif key == "E":
            lines.append(f"- 计分规则：{ALGORITHM_SCORING_RULE}")
            lines.append(f"- 每日最低目标：{ALGORITHM_DAILY_TARGET_POINTS} 分")
            lines.append(f"- 本周重点题型：{', '.join(phase['algorithm_focus'])}")
            lines.append(f"- 错题复盘要求：{module['minimum']}")
        elif key == "F":
            lines.append(f"- 当前状态：{module['goal']}")
            lines.append("- 发布节奏：暂停；不生成发布、草稿或选题任务。")
            lines.append(f"- 最低完成标准：{module['minimum']}")
        elif key == "G":
            lines.append(f"- 当前状态：{module['goal']}")
            lines.append("- 调整规则：考试暂停期间不生成考试复习任务。")
            lines.append(f"- 最低完成标准：{module['minimum']}")
        else:
            lines.append(f"- 最低完成标准：{module['minimum']}")
            lines.append(f"- 可加码内容：{module['stretch']}")
        lines.append("")

    lines.extend(
        [
            "## 5. 本周不可砍任务",
            md_list(phase["non_negotiable"][:5]),
            "",
            "## 6. 本周可砍任务",
            md_list(phase["cuttable"][:5]),
            "",
            "## 7. 每日动态计划规则",
            "- 每天先复盘昨日完成情况，再生成今日计划。",
            "- 今日计划必须从本周计划派生，不能孤立加新主线。",
            "- 考试暂时结束，不参与每日任务加权。",
            "- 简历项目连续 2 天无实质推进时，第三天简历项目必须升为 P0。",
            f"- 算法每天至少 {ALGORITHM_DAILY_TARGET_POINTS} 分；{ALGORITHM_SCORING_RULE}；连续两天低于目标时，第三天必须补足并做错题复盘。",
            "- 小红书计划暂停，不参与每日任务加权。",
            "- 昨日完成度 < 60% 或精力 <= 5/10 时，今日自动降载。",
            "",
            "## 8. 风险提醒",
            "- 简历项目被泛学习稀释，导致没有可投递材料。",
            "- 算法用题数而不是难度计分，导致训练强度失真。",
            "- 前沿学习开新坑，不能反哺项目、简历或面试。",
            "",
            "## 9. 本周成功标准",
            "- 本周不可砍任务全部有明确产出。",
            "- 简历项目比本周开始时更可展示、可追问、可投递。",
            "- 算法保持连续，且有错题 / 模板沉淀。",
            "- 每日计划和复盘都落档到 Obsidian。",
        ]
    )
    return front + "\n".join(lines) + "\n"


def apply_weekly_policy_to_text(text: str) -> str:
    text = clean_duplicate_leading_frontmatter(text)
    if not XIAOHONGSHU_PAUSED and not EXAMS_PAUSED:
        return text

    replacements = {}
    if EXAMS_PAUSED:
        replacements.update(
            {
                "考试周 + 简历项目启动周": "简历项目启动周",
                "高强度项目冲刺周 + 6 月 29 日考试预备周": "高强度项目冲刺周",
                "考试日 + 实习低强度过渡周": "实习低强度过渡周",
                "- 为 6 月 18 日考试留出复习时间。\n": "- 考试暂时结束，不纳入每日任务加权。\n",
                "- 6 月 25 日起逐步提高 6 月 29 日考试复习权重。\n": "- 考试暂时结束，不纳入每日任务加权。\n",
                "- 6 月 29 日完成考试。\n": "- 考试暂时结束，不纳入每日任务加权。\n",
                "- P0：简历项目整理与工程化；考试前 3 天自动切换为考试复习 P0。\n": "- P0：简历项目整理与工程化。\n",
                "- P1：考试复习与缓冲。\n": "- P1：缓冲与复盘。\n",
                "- 6 月 18 日考试复习。\n": "",
                "- 考试。\n": "",
                "- 距离考试 <= 3 天时，考试复习自动升为 P0。\n": "- 考试暂时结束，不参与每日任务加权。\n",
                "- 考试临近时仍安排重型开发，造成复习失控。\n": "- 算法用题数而不是难度计分，导致训练强度失真。\n",
                "- 本周目标：本周 10-12 道，考试前可降到每天 1 道。\n": f"- 本周目标：每天至少 {ALGORITHM_DAILY_TARGET_POINTS} 分，按难度计分。\n",
                "- 本周目标题数：10-12 道\n": f"- 计分规则：{ALGORITHM_SCORING_RULE}\n- 每日最低目标：{ALGORITHM_DAILY_TARGET_POINTS} 分\n",
                "- 错题复盘要求：不能连续两天为 0；周内整理错题和模板。\n": f"- 错题复盘要求：每日最低 {ALGORITHM_DAILY_TARGET_POINTS} 分（{ALGORITHM_SCORING_RULE}）；不能连续两天低于目标；记录题型、错因和模板。\n",
                "- 算法不能连续两天为 0；连续两天低于目标时，第三天至少安排 2 道并做错题复盘。\n": f"- 算法每天至少 {ALGORITHM_DAILY_TARGET_POINTS} 分；{ALGORITHM_SCORING_RULE}；连续两天低于目标时，第三天必须补足并做错题复盘。\n",
            }
        )

    if XIAOHONGSHU_PAUSED:
        replacements.update({
        "- 保持小红书两天一篇的内容节奏。\n": "- 小红书计划暂停，不纳入本周交付。\n",
        "- 保持小红书两天一篇。\n": "- 小红书计划暂停，不纳入本周交付。\n",
        "- 保持算法、小红书、前沿学习不断档。\n": "- 保持算法和前沿学习不断档。\n",
        "- 保持算法、AI 前沿、小红书不断档，但降低每日负担。\n": "- 保持算法和 AI 前沿不断档，但降低每日负担。\n",
        "- P3：AI 前沿 / 热门架构学习，必须能服务简历、工作台、面试或小红书。\n": "- P3：AI 前沿 / 热门架构学习，必须能服务简历、工作台或面试。\n",
        "- P4：长期技术栈补充与小红书保底发布。\n": "- P4：长期技术栈补充。\n",
        "- P4：前沿学习、技术栈补充、小红书保底发布。\n": "- P4：前沿学习、技术栈补充。\n",
        "- P4：小红书和技术栈维护。\n": "- P4：技术栈维护。\n",
        "- 小红书至少 2 篇。\n": "",
        "- 小红书过度打磨。\n": "- 小红书发布、草稿和选题打磨。\n",
        "- 过长的小红书选题研究。\n": "- 小红书发布、草稿和选题打磨。\n",
        "- 复杂小红书内容。\n": "- 小红书发布、草稿和选题打磨。\n",
        "- 如何复用到项目 / 小红书 / 面试：必须映射到简历项目、多 Agent 工作台、小红书或面试表达之一。\n": "- 如何复用到项目 / 面试：必须映射到简历项目、多 Agent 工作台或面试表达之一。\n",
        "- 如何复用到项目 / 小红书 / 面试：反哺工作台模块设计、小红书选题和面试表达。\n": "- 如何复用到项目 / 面试：反哺工作台模块设计和面试表达。\n",
        "- 如何复用到项目 / 小红书 / 面试：输出面向项目、面试或小红书。\n": "- 如何复用到项目 / 面试：输出面向项目或面试。\n",
        "- 小红书距离上次发布 >= 2 天时，当天必须安排发布或发布草稿。\n": "- 小红书计划暂停，不参与每日任务加权。\n",
        "- 小红书和前沿学习开新坑，不能反哺项目、简历或面试。\n": "- 前沿学习开新坑，不能反哺项目、简历或面试。\n",
        "- 小红书保持两天一篇或至少完成草稿节奏。\n": "",
        })
    for old, new in replacements.items():
        text = text.replace(old, new)

    if XIAOHONGSHU_PAUSED:
        paused_block = "\n".join(
            [
                "### F. 内容发布（暂停）",
                "- 当前状态：暂停：暂不安排发布、草稿和选题，只保留已有素材。",
                "- 发布节奏：暂停；不生成发布、草稿或选题任务。",
                "- 最低完成标准：暂停期间不生成每日发布任务。",
                "",
            ]
        )
        text = re.sub(r"### F\. .*?\n(?=### G\. )", paused_block, text, count=1, flags=re.DOTALL)
    if EXAMS_PAUSED:
        paused_exam_block = "\n".join(
            [
                "### G. 考试复习与缓冲（暂停）",
                "- 当前状态：暂停：考试暂时结束，不生成复习任务。",
                "- 调整规则：考试暂停期间不生成考试 P0 / P1。",
                "- 最低完成标准：暂停期间不安排考试任务，只保留必要缓冲。",
                "",
            ]
        )
        text = re.sub(r"### G\. .*?\n(?=## 5\. )", paused_exam_block, text, count=1, flags=re.DOTALL)
    return text


def ensure_weekly_plan(ctx: WorkstationContext, day: date) -> tuple[WriteResult, dict[str, Any], Path]:
    phase = phase_for(day)
    path = weekly_plan_path(ctx, phase)
    if path.exists():
        text = clean_duplicate_leading_frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
        updated = apply_weekly_policy_to_text(text)
        if updated != text:
            return write_text_file(path, updated, overwrite=True), phase, path
        return WriteResult(path, "skipped"), phase, path
    return write_text_file(path, render_weekly_plan(ctx, phase), overwrite=False), phase, path


def nearest_exam(day: date) -> tuple[date | None, int | None]:
    if EXAMS_PAUSED:
        return None, None
    future = [(exam, (exam - day).days) for exam in EXAMS if (exam - day).days >= 0]
    if not future:
        return None, None
    return min(future, key=lambda item: item[1])


def exam_mode(day: date) -> str:
    exam, days = nearest_exam(day)
    if exam is None or days is None:
        return "normal"
    if days == 0:
        return "exam_day"
    if days <= 1:
        return "exam_eve"
    if days <= 3:
        return "exam_p0"
    if exam == date(2026, 6, 29) and days <= 5:
        return "exam_weighted"
    return "normal"


def daily_note_path(ctx: WorkstationContext, day: date) -> Path:
    return configured_path(ctx, "daily_dir") / f"{day.isoformat()}.md"


def read_daily(ctx: WorkstationContext, day: date) -> str:
    path = daily_note_path(ctx, day)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def marked_section(text: str, marker: str) -> str:
    pattern = re.compile(
        rf"<!-- BEGIN {re.escape(marker)} -->(.*?)<!-- END {re.escape(marker)} -->",
        re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def clean_daily_note_text(text: str) -> str:
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return text
    front_lines = [
        line
        for line in parts[1].splitlines()
        if not re.match(r"^(preview|human_review_required|human_reviewed):\s*", line)
    ]
    while front_lines and not front_lines[0].strip():
        front_lines.pop(0)
    front = "\n".join(front_lines)
    return f"---\n{front}\n---{parts[2]}"


def clean_duplicate_leading_frontmatter(text: str) -> str:
    pattern = re.compile(r"^\ufeff?---\s*\r?\n.*?\r?\n---\s*(?=\ufeff?---\s*\r?\n)", re.DOTALL)
    while pattern.match(text):
        text = pattern.sub("", text, count=1)
    return text.lstrip("\ufeff")


def checkbox_stats(text: str) -> dict[str, Any]:
    done: list[str] = []
    open_items: list[str] = []
    for line in text.splitlines():
        match = re.match(r"\s*-\s+\[([ xX])\]\s+(.+)", line)
        if not match:
            continue
        checked, body = match.groups()
        if checked.lower() == "x":
            done.append(body.strip())
        else:
            open_items.append(body.strip())
    total = len(done) + len(open_items)
    score = round((len(done) / total) * 10, 1) if total else None
    return {"done": done, "open": open_items, "total": total, "score": score}


def apply_daily_review_policy(items: list[str]) -> list[str]:
    if not XIAOHONGSHU_PAUSED and not EXAMS_PAUSED:
        return items

    filtered: list[str] = []
    for item in items:
        if XIAOHONGSHU_PAUSED and re.search(r"小红书|XHS", item, re.IGNORECASE):
            continue
        if EXAMS_PAUSED and re.search(r"考试|复习", item):
            continue
        if re.search(r"算法.*(?:\d+\s*-\s*\d+\s*道|至少\s*\d+\s*道|\d+\s*道)", item) and "分" not in item:
            continue
        filtered.append(
            item.replace("或小红书", "")
            .replace("、小红书", "")
            .replace("小红书、", "")
            .replace(" / 考试", "")
            .replace("考试 / ", "")
        )
    return filtered


def parse_energy(text: str) -> int | None:
    match = re.search(r"精力\s*[:：]\s*(\d{1,2})\s*/\s*10", text)
    if not match:
        return None
    return max(0, min(10, int(match.group(1))))


def yesterday_review(ctx: WorkstationContext, day: date) -> dict[str, Any]:
    yesterday = day - timedelta(days=1)
    text = read_daily(ctx, yesterday)
    if not text:
        return {
            "date": yesterday,
            "exists": False,
            "score": None,
            "energy": None,
            "done": [],
            "open": [],
            "summary": "没有找到昨日 Daily Note，本次从本周计划基线生成今日计划。",
        }
    plan_section = marked_section(text, "PERSONAL_WORKSTATION_DYNAMIC_PLAN") or text
    stats = checkbox_stats(plan_section)
    done = apply_daily_review_policy(stats["done"])
    open_items = apply_daily_review_policy(stats["open"])
    energy = parse_energy(plan_section)
    summary = "已读取昨日动态计划区块。" if stats["total"] else "昨日有 Daily Note，但没有可解析的动态计划 checkbox。"
    return {
        "date": yesterday,
        "exists": True,
        "score": stats["score"],
        "energy": energy,
        "done": done,
        "open": open_items,
        "summary": summary,
    }


def checked_line_contains(ctx: WorkstationContext, day: date, pattern: str) -> bool:
    text = read_daily(ctx, day)
    section = marked_section(text, "PERSONAL_WORKSTATION_DYNAMIC_PLAN") or text
    for line in section.splitlines():
        if re.match(r"\s*-\s+\[[xX]\]\s+", line) and re.search(pattern, line, re.IGNORECASE):
            return True
    return False


def resume_stalled(ctx: WorkstationContext, day: date) -> bool:
    checked_days = [
        checked_line_contains(ctx, day - timedelta(days=offset), r"简历|resume|STAR|bullet|项目包装|toB|短剧")
        for offset in (1, 2)
        if read_daily(ctx, day - timedelta(days=offset))
    ]
    return len(checked_days) == 2 and not any(checked_days)


def algorithm_low_two_days(ctx: WorkstationContext, day: date) -> bool:
    checked_days = [
        checked_line_contains(ctx, day - timedelta(days=offset), r"算法|Hot100|错题")
        for offset in (1, 2)
        if read_daily(ctx, day - timedelta(days=offset))
    ]
    return len(checked_days) == 2 and not any(checked_days)


def last_checked_date(ctx: WorkstationContext, day: date, pattern: str) -> date | None:
    for offset in range(1, 15):
        candidate = day - timedelta(days=offset)
        if checked_line_contains(ctx, candidate, pattern):
            return candidate
    return None


def select_by_offset(items: list[Any], day: date, phase: dict[str, Any]) -> Any:
    if not items:
        return ""
    offset = max(0, (day - phase["start"]).days)
    return items[offset % len(items)]


def xhs_due(ctx: WorkstationContext, day: date, phase: dict[str, Any]) -> bool:
    if XIAOHONGSHU_PAUSED:
        return False
    last = last_checked_date(ctx, day, r"小红书|XHS")
    if last:
        return (day - last).days >= 2
    return (day - phase["start"]).days >= 1


def today_progress_lines(existing_text: str) -> list[str]:
    if not existing_text:
        return []
    section = marked_section(existing_text, "PERSONAL_WORKSTATION_DYNAMIC_PLAN") or existing_text
    stats = checkbox_stats(section)
    return apply_daily_review_policy(stats["done"])


def today_external_progress(ctx: WorkstationContext, day: date) -> list[str]:
    progress: list[str] = []
    for item in collect_learning_notes(ctx, day.isoformat()):
        progress.append(f"学习记录：{item['topic']} · area={item['area']} · status={item['status']}")

    algorithm_root = ctx.target_root / "06_Learning" / "算法"
    if algorithm_root.exists():
        for path in sorted(algorithm_root.rglob("*.md")):
            if path.stem.lower() == "index":
                continue
            modified_day = date.fromtimestamp(path.stat().st_mtime)
            if modified_day == day:
                progress.append(f"算法笔记更新：{path.stem}")
    return progress


def render_daily_plan(ctx: WorkstationContext, day: date, phase: dict[str, Any], existing_text: str = "") -> str:
    review = yesterday_review(ctx, day)
    mode = exam_mode(day)
    exam, exam_days = nearest_exam(day)
    stalled = resume_stalled(ctx, day)
    algo_low = algorithm_low_two_days(ctx, day)
    due_xhs = xhs_due(ctx, day, phase)
    fatigue = (review["score"] is not None and review["score"] < 6) or (
        review["energy"] is not None and review["energy"] <= 5
    )

    resume_task = select_by_offset(phase["resume_daily"], day, phase)
    agent_task = select_by_offset(phase["agent_daily"], day, phase)
    frontier_topic = select_by_offset(phase["frontier_topics"], day, phase)
    tech_topic, tech_feature = select_by_offset(phase["tech_stack"], day, phase)

    algorithm_target = f"{ALGORITHM_DAILY_TARGET_POINTS} 分（{ALGORITHM_SCORING_RULE}）"

    p0: list[str]
    p1: list[str]
    if mode == "exam_day":
        p0 = ["完成今日考试；考后只做轻量复盘和休息，不安排重型开发。"]
        p1 = [f"轻量整理考试错题 / 记忆点；算法按状态完成，目标仍参考 {algorithm_target}。"]
    elif mode == "exam_eve":
        p0 = ["考试复习：回顾重点知识点、错题、记忆型内容，不安排复杂代码开发。"]
        p1 = [f"简历项目轻量推进：{resume_task}"]
    elif mode == "exam_p0":
        p0 = ["考试复习升为 P0：完成核心范围复习和错题回顾。"]
        p1 = [f"简历项目降载推进：{resume_task}", f"算法 Hot100 至少 {algorithm_target}。"]
    elif stalled:
        p0 = [f"简历项目补推进：{resume_task}"]
        p1 = [f"多 Agent 工作台轻量设计：{agent_task}", f"算法 Hot100 至少 {algorithm_target}。"]
    else:
        p0 = [f"简历项目整理与工程化：{resume_task}"]
        p1 = [f"多 Agent 协作工作台：{agent_task}", f"算法 Hot100 至少 {algorithm_target}。"]
        if mode == "exam_weighted":
            p1.insert(0, "6 月 29 日考试复习加权：梳理考试范围和重点知识点。")
        elif exam and exam_days is not None:
            p1.append(f"考试复习：距离 {exam.isoformat()} 还有 {exam_days} 天，至少完成一段复习。")

    minimum = [
        f"算法 Hot100：至少 {algorithm_target}，并记录每题难度、题型、错因 / 模板。",
        f"AI 前沿学习：{frontier_topic}，输出 5-8 条能服务项目、简历或面试的笔记。",
        f"长期技术栈：{tech_topic}，绑定功能：{tech_feature}，必须有小产出。",
        "晚间复盘：补全完成项、未完成项、耗时、精力 / 专注 / 焦虑 / 睡眠评分。",
    ]

    optional = []
    if not fatigue and mode == "normal":
        optional.append(f"可加码 1 个项目推进任务：把「{agent_task}」沉淀成 README / 架构说明。")
    if not optional:
        optional.append("只在 P0 和保底任务完成后，再做 15-30 分钟资料整理。")

    adjustments = []
    if mode == "exam_day":
        adjustments.append("考试当天：任务自动降为考试 + 轻量复盘。")
    elif mode in {"exam_eve", "exam_p0"}:
        adjustments.append("距离考试 <= 3 天：考试复习升为 P0。")
    elif mode == "exam_weighted":
        adjustments.append("6 月 29 日考试进入预热期：提高复习权重。")
    elif EXAMS_PAUSED:
        adjustments.append("考试暂时结束：今日不生成考试复习任务。")
    if stalled:
        adjustments.append("检测到简历项目近两天缺少已完成推进项：今日简历项目强制 P0。")
    if algo_low:
        adjustments.append(f"检测到算法近两天缺少已完成项：今日算法至少 {algorithm_target} 并做错题复盘。")
    if XIAOHONGSHU_PAUSED:
        adjustments.append("小红书计划暂停：今日不生成发布、草稿或选题任务。")
    if fatigue:
        adjustments.append("昨日完成度或精力偏低：今日降载，保留 P0 和最低保底任务。")
    if not adjustments:
        adjustments.append("未触发强制降载 / 加权规则，按本周基线计划推进。")

    score_text = "暂无可计算评分" if review["score"] is None else f"{review['score']}/10"
    energy_text = "未记录" if review["energy"] is None else f"{review['energy']}/10"
    done_lines = md_list(review["done"][:6]) if review["done"] else "- 暂无可解析完成项。"
    open_lines = md_list(review["open"][:8]) if review["open"] else "- 暂无可解析未完成项。"
    today_done = today_progress_lines(existing_text) + today_external_progress(ctx, day)
    today_done = list(dict.fromkeys(today_done))
    today_scan_block: list[str] = []
    if today_done:
        today_scan_block = [
            "### 今日已完成扫描",
            md_list(today_done[:8]),
            "",
        ]

    return "\n".join(
        [
            "## 动态日计划",
            f"- generated_by: personal_workstation.plan_automation",
            f"- generated_at: {now_iso(ctx)}",
            f"- weekly_plan: [[{weekly_plan_path(ctx, phase).relative_to(ctx.target_root).as_posix()}|{format_day(phase['start'])} - {format_day(phase['end'])}]]",
            "",
            "### 昨日复盘",
            f"- 复盘日期：{review['date'].isoformat()}",
            f"- 自动评分：{score_text}",
            f"- 精力：{energy_text}",
            f"- 说明：{review['summary']}",
            "",
            "#### 昨日完成",
            done_lines,
            "",
            "#### 昨日未完成",
            open_lines,
            "",
            "### 今日动态调整",
            md_list(adjustments),
            "",
            *today_scan_block,
            "### 今日 P0 任务",
            md_list(p0, checkbox=True),
            "",
            "### 今日 P1 任务",
            md_list(p1, checkbox=True),
            "",
            "### 今日最低保底任务",
            md_list(minimum, checkbox=True),
            "",
            "### 今日可选加码任务",
            md_list(optional, checkbox=True),
            "",
            "### 今日交付物",
            md_list(
                [
                    "Daily Note 中完成 / 未完成 checkbox 可复盘。",
                    "至少一个简历 / 项目 / 算法相关产出能被追踪。",
                    "前沿学习或技术栈笔记能映射到简历、工作台或面试。",
                ],
                checkbox=True,
            ),
            "",
            "### 晚间复盘输入",
            "- 完成了什么：",
            "- 没完成什么：",
            "- 为什么没完成：",
            "- 每项任务耗时：",
            "- 算法完成数量：",
            "- 前沿学习主题：",
            "- 技术栈学习内容：",
            "- 简历 / 项目推进：",
            "- 其他缓冲事项：",
            "- 精力：/10",
            "- 专注：/10",
            "- 焦虑：/10",
            "- 睡眠：/10",
            "",
            "### 未完成任务处理区",
            "#### 必须顺延",
            "- [ ] ",
            "",
            "#### 可以降级",
            "- [ ] ",
            "",
            "#### 直接删除",
            "- [ ] ",
        ]
    )


def write_daily_plan(ctx: WorkstationContext, day: date, phase: dict[str, Any]) -> WriteResult:
    path = daily_note_path(ctx, day)
    if not path.exists():
        create_daily_note(ctx, day.isoformat())
    text = clean_daily_note_text(path.read_text(encoding="utf-8", errors="ignore"))
    updated = upsert_marked_section(
        text,
        "PERSONAL_WORKSTATION_DYNAMIC_PLAN",
        render_daily_plan(ctx, day, phase, existing_text=text),
    )
    return write_text_file(path, updated, overwrite=True)


def update_weekly_adjustment(ctx: WorkstationContext, day: date, phase: dict[str, Any]) -> WriteResult:
    path = weekly_plan_path(ctx, phase)
    text = clean_duplicate_leading_frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
    review = yesterday_review(ctx, day)
    mode = exam_mode(day)
    score = "暂无" if review["score"] is None else f"{review['score']}/10"
    content = "\n".join(
        [
            "## 本周动态调整记录",
            f"- updated_at: {now_iso(ctx)}",
            f"- today: {day.isoformat()}",
            f"- yesterday_score: {score}",
            f"- exam_mode: {mode}",
            f"- resume_stalled: {str(resume_stalled(ctx, day)).lower()}",
            f"- algorithm_low_two_days: {str(algorithm_low_two_days(ctx, day)).lower()}",
            f"- xiaohongshu_due: {str(xhs_due(ctx, day, phase)).lower()}",
            "",
            "### 今日解释",
            "本区块由每日计划自动化更新，用于记录本周剩余计划的动态权重变化。完整任务清单以 Daily Note 的 `PERSONAL_WORKSTATION_DYNAMIC_PLAN` 区块为准。",
        ]
    )
    updated = upsert_marked_section(text, "PERSONAL_WORKSTATION_WEEKLY_ADJUSTMENT", content)
    return write_text_file(path, updated, overwrite=True)


def adjust_plan(ctx: WorkstationContext, note_date: str | None = None, *, weekly_only: bool = False) -> list[WriteResult]:
    day = parse_day(ctx, note_date)
    weekly_result, phase, _path = ensure_weekly_plan(ctx, day)
    results = [weekly_result]
    if weekly_only:
        return results
    results.append(write_daily_plan(ctx, day, phase))
    results.append(update_weekly_adjustment(ctx, day, phase))
    results.append(sync_daily(ctx, day.isoformat()))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate weekly and daily dynamic plans into Obsidian.")
    parser.add_argument("--config", default=None)
    parser.add_argument("--date", default=None)
    parser.add_argument("--weekly-only", action="store_true")
    args = parser.parse_args()
    ctx = make_context(args.config)
    for result in adjust_plan(ctx, args.date, weekly_only=args.weekly_only):
        print(f"{result.action}: {result.path}")


if __name__ == "__main__":
    main()
