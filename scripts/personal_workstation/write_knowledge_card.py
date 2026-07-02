from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.personal_workstation.common import (  # noqa: E402
    WorkstationContext,
    configured_path,
    frontmatter,
    make_context,
    safe_slug,
    stable_id,
    today_string,
    write_text_file,
)


def knowledge_card_content(ctx: WorkstationContext, topic: str, domain: str) -> str:
    return frontmatter(
        {
            "type": "knowledge-card",
            "id": stable_id("knowledge", topic),
            "topic": topic,
            "domain": domain,
            "source": "codex",
            "human_reviewed": False,
            "human_review_required": True,
            "confidence": "medium",
            "preview": bool(ctx.config.get("preview_mode", True)),
            "created": today_string(ctx),
            "updated": today_string(ctx),
        },
        ["knowledge"],
    ) + f"""# {topic}

## 一句话解释
本地优先的个人 AI 工作站把日常工作、项目推进、Codex 任务和长期知识沉淀到同一个可复盘系统中。

## 适用场景
- 每日工作记录
- 项目进度追踪
- Codex 任务审计
- 长期知识复盘
- 后续本地 RAG / 多 Agent 工作流

## 核心概念
- Local-first：默认写入本地文件。
- Obsidian-first：长期阅读和复盘入口是 Markdown vault。
- Audit-friendly：每条自动记录都标注来源、生成时间和审核状态。
- Visualization-ready：同时输出结构化 JSON 和静态 Dashboard。

## 常见误区
- 不应把它写成某个具体项目的专用笔记工具。
- preview 产物不能等同于人工确认结论。
- Dashboard 是观察入口，不是唯一数据源。

## 和其他概念的区别
- 和普通笔记不同：它强调结构化、可验证、可自动写入。
- 和项目管理工具不同：它服务于个人长期知识沉淀，不只追任务。
- 和 RAG 系统不同：MVP 只准备结构，不直接做 embedding。

## 在我当前项目/学习中的应用
- 先把 Codex 工作结果写入 `03_Codex_Tasks/`。
- 再把稳定结论沉淀为 `04_Knowledge/` 卡片。
- 最后通过周/月复盘提炼长期路线。

## 相关链接
- [[00_Home/Dashboard]]
- [[02_Projects/Personal_AI_Workstation/Current_Status]]

## 审核状态
- human_reviewed: false
- human_review_required: true
"""


def create_knowledge_card(
    ctx: WorkstationContext,
    topic: str = "个人 AI 工作站的本地优先知识沉淀",
    domain: str = "AI",
):
    domain_dir = configured_path(ctx, "knowledge_dir") / safe_slug(domain, "AI")
    path = domain_dir / f"{safe_slug(topic)}.md"
    return write_text_file(
        path,
        knowledge_card_content(ctx, topic, domain),
        overwrite=bool(ctx.config.get("allow_overwrite", False)),
        unique_on_conflict=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a knowledge card.")
    parser.add_argument("--config", default=None)
    parser.add_argument("--topic", default="个人 AI 工作站的本地优先知识沉淀")
    parser.add_argument("--domain", default="AI")
    args = parser.parse_args()
    ctx = make_context(args.config)
    result = create_knowledge_card(ctx, args.topic, args.domain)
    print(f"{result.action}: {result.path}")


if __name__ == "__main__":
    main()
