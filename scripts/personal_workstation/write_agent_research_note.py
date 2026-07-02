from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.personal_workstation.common import (  # noqa: E402
    WorkstationContext,
    frontmatter,
    make_context,
    safe_slug,
    stable_id,
    today_string,
    write_text_file,
)


SOURCE_PRIORITY = [
    "OpenAI",
    "Anthropic",
    "Google",
    "Microsoft",
    "LangChain",
    "vLLM",
    "Ray",
    "OpenTelemetry",
    "OWASP",
    "major vector DBs",
    "arXiv engineering papers",
    "GitHub releases",
]


FALLBACK_TOPICS = [
    {
        "priority": "P0-01",
        "topic": "Agent Harness / Agent Loop",
        "learn_focus": "plan -> act -> observe -> update state；工具调用、sandbox、审批、上下文压缩、失败恢复。",
        "interview_value": "这是 Agent 工程化的核心，不是“套个 Agent 框架”。",
        "summary": "Agent Harness 的价值是把模型、工具、权限、状态和失败恢复编排成可复现的工程闭环。",
        "core_architecture": [
            "User goal 进入 harness 后先变成 task state，而不是直接让模型自由发挥。",
            "Agent loop 每轮执行 plan、act、observe、state update，直到满足停止条件或触发人工审批。",
            "Harness 负责上下文裁剪、工具沙箱、失败恢复、产物写入和 trace 记录。",
        ],
        "key_modules": [
            "Planner：把目标拆成可执行步骤，并给出需要的工具。",
            "Tool runtime：执行只读/写入/高风险工具，处理权限和审批。",
            "State store：保存任务状态、上下文摘要、工具结果和失败原因。",
            "Recovery policy：处理重试、降级、回滚、转人工。",
        ],
        "engineering_implementation": [
            "为本地 Obsidian 工作站定义 task_state.json：goal、plan、current_step、artifacts、errors。",
            "把写文件、搜索、刷新索引拆成不同权限等级的工具。",
            "每次工具调用记录 trace_id、tool_name、arguments_hash、result_status、human_review_required。",
        ],
        "interview_questions": [
            "Agent loop 和普通 while-loop 的区别是什么？",
            "如何避免 Agent 在失败后无限重试？",
            "为什么 harness 要负责上下文管理，而不是只靠模型 prompt？",
        ],
        "mini_demo": [
            "用一个 Markdown JSON 文件模拟 task state。",
            "写 3 个 mock tool：search_notes、write_note、refresh_index。",
            "跑一个 3 步任务并输出 trace.md，展示失败重试和人工审批标记。",
        ],
        "xiaohongshu": [
            "标题：为什么真正的 Agent 不是一个聊天框，而是一套任务执行系统？",
            "用“实习生 + 工具箱 + 操作日志”的类比解释 harness。",
            "结尾展示一张 plan/act/observe/update state 流程图。",
        ],
    },
    {
        "priority": "P0-02",
        "topic": "MCP：Model Context Protocol",
        "learn_focus": "host/client/server、tools、resources、prompts、auth、权限、安全、MCP server 设计。",
        "interview_value": "工具接入、企业数据接入、AgentOps 高频。",
        "summary": "MCP 把模型可用的外部能力标准化成 server 暴露的 tools、resources 和 prompts。",
        "core_architecture": [
            "Host 承载模型和用户工作流，Client 负责与 MCP server 建立连接。",
            "Server 暴露 tools、resources、prompts，让 Agent 以统一协议访问外部系统。",
            "权限、安全和审计应放在 server 边界，而不是散落在 prompt 里。",
        ],
        "key_modules": [
            "Tools：可执行动作，例如搜索、写入、查询数据库。",
            "Resources：可读取上下文，例如文件、文档、配置、知识库条目。",
            "Prompts：可复用任务模板。",
            "Auth/audit：身份、授权、调用日志和风险控制。",
        ],
        "engineering_implementation": [
            "先为个人工作站设计只读 MCP server：list_notes、read_note、search_index。",
            "工具返回值要短、结构化，并包含 source_path 和 confidence。",
            "写入类工具必须加 human_review_required 或审批开关。",
        ],
        "interview_questions": [
            "MCP server 和普通 REST API 包装有什么区别？",
            "MCP 的 tools 和 resources 该如何划分？",
            "企业里如何控制 Agent 通过 MCP 访问敏感数据？",
        ],
        "mini_demo": [
            "写一个本地 notes MCP server，仅暴露 read/search 两个只读工具。",
            "构造 5 条笔记，让 Agent 根据 search 结果回答并附引用。",
            "记录每次 tool call 的输入输出，做成审计表。",
        ],
        "xiaohongshu": [
            "标题：MCP 到底解决了什么？一句话：给 AI 接工具的 USB-C。",
            "用“插座标准”解释 host/client/server。",
            "强调 MCP 不等于万能安全，权限边界仍要自己设计。",
        ],
    },
    {
        "priority": "P0-03",
        "topic": "A2A：Agent-to-Agent Protocol",
        "learn_focus": "Agent Card、Task、Message、Artifact、streaming、agent 发现与委托。",
        "interview_value": "多 Agent 系统互操作，适合讲“跨框架协作”。",
        "summary": "A2A 的重点是让不同 Agent 能发现彼此、委托任务、交换消息并交付 artifact。",
        "core_architecture": [
            "Agent Card 描述一个 Agent 的能力、入口、认证方式和交付格式。",
            "Task 是跨 Agent 协作的核心对象，Message 承载沟通，Artifact 承载结果。",
            "Streaming 让长任务可以持续回传状态，而不是只等最终答案。",
        ],
        "key_modules": [
            "Discovery：查找可用 Agent 及其能力。",
            "Delegation：把任务和约束交给另一个 Agent。",
            "Artifact exchange：传递代码、文档、图表、报告等产物。",
            "Status streaming：展示任务进度和中间状态。",
        ],
        "engineering_implementation": [
            "为个人工作站定义 Research Agent、Writer Agent、Reviewer Agent 的 Agent Card。",
            "让 Research Agent 产出 sources.json，Writer Agent 产出 Markdown，Reviewer Agent 检查空泛内容。",
            "用 artifact_id 串起跨 Agent 的输入输出。",
        ],
        "interview_questions": [
            "A2A 和 MCP 的边界分别是什么？",
            "什么时候需要多 Agent，什么时候单 Agent 加工具就够？",
            "跨 Agent 委托时如何保证结果可审计？",
        ],
        "mini_demo": [
            "用 3 个本地函数模拟 3 个 Agent。",
            "定义 agent_card.json 和 task.json。",
            "让任务从 research -> write -> review 流转，并输出 artifacts/trace.md。",
        ],
        "xiaohongshu": [
            "标题：AI 之间也需要“工单系统”：A2A 是怎么让 Agent 协作的？",
            "用公司协作类比 Agent Card、Task、Artifact。",
            "展示单 Agent 与多 Agent 的边界判断。",
        ],
    },
    {
        "priority": "P0-04",
        "topic": "AG-UI：Agent-User Interaction",
        "learn_focus": "SSE/WebSocket streaming、状态同步、human-in-the-loop、前端工具调用。",
        "interview_value": "做 demo、管理台、可视化 Agent 流程很有用。",
        "summary": "AG-UI 关注 Agent 与用户界面的实时协作：状态、事件、审批和工具结果都要可视化。",
        "core_architecture": [
            "后端 Agent runtime 通过 SSE 或 WebSocket 推送事件。",
            "前端维护任务状态机，展示 plan、tool call、observation、artifact。",
            "Human-in-the-loop 事件让用户能批准、拒绝或补充上下文。",
        ],
        "key_modules": [
            "Event stream：token、status、tool_call、approval_request、artifact_ready。",
            "State reducer：把事件折叠成当前 UI 状态。",
            "Approval panel：处理高风险工具调用。",
            "Artifact viewer：预览文档、表格、代码、日志。",
        ],
        "engineering_implementation": [
            "为个人工作站 dashboard 增加 trace timeline 的数据结构。",
            "把工具调用分成 pending、running、done、failed 四种 UI 状态。",
            "高风险写入前显示 diff 和审批按钮。",
        ],
        "interview_questions": [
            "为什么 Agent UI 不能只展示最终回答？",
            "SSE 和 WebSocket 在 Agent 场景下如何选择？",
            "Human-in-the-loop 应该阻塞在哪里？",
        ],
        "mini_demo": [
            "写一个本地静态页面读取 trace_events.jsonl。",
            "把事件渲染成时间线。",
            "模拟一个 approval_request，点击批准后继续显示 artifact_ready。",
        ],
        "xiaohongshu": [
            "标题：为什么 Agent 产品要做“过程可视化”，而不是只做聊天框？",
            "截图展示工具调用时间线。",
            "用“看得见过程，才敢交给 AI 做事”收尾。",
        ],
    },
    {
        "priority": "P0-05",
        "topic": "OpenAI Agents SDK / Google ADK / Microsoft Agent Framework",
        "learn_focus": "agents、handoffs、guardrails、sessions、workflow、MCP/A2A 集成。",
        "interview_value": "能解释不同 Agent runtime 的抽象差异。",
        "summary": "主流 Agent SDK 的共同点是把模型调用、工具、状态、交接、护栏和追踪变成 runtime 抽象。",
        "core_architecture": [
            "Agent 定义 instructions、tools、output schema 和执行策略。",
            "Session 或 state 管理跨轮上下文。",
            "Handoff/workflow 处理多 Agent 或多步骤任务编排。",
            "Tracing/guardrails 负责可观测性与安全边界。",
        ],
        "key_modules": [
            "Agent definition：角色、指令、工具和输出格式。",
            "Tool adapter：把外部系统接入 runtime。",
            "Guardrails：输入输出校验、权限和安全策略。",
            "Tracing：记录 generation、tool call、handoff、guardrail 事件。",
        ],
        "engineering_implementation": [
            "用同一个任务分别写成 OpenAI Agents SDK 风格、LangGraph 风格和普通 loop 风格的伪代码。",
            "比较状态、工具、handoff 和 trace 的差异。",
            "把比较结果写进面试项目讲解稿。",
        ],
        "interview_questions": [
            "Agent SDK 和 LangGraph 这类 stateful runtime 的取舍是什么？",
            "handoff 和 tool call 的差别是什么？",
            "guardrail 应该放在模型前、工具前还是输出后？",
        ],
        "mini_demo": [
            "选一个“检索资料并写 Obsidian 笔记”的任务。",
            "画出三种 runtime 的执行图。",
            "实现最小伪代码并比较 trace 字段。",
        ],
        "xiaohongshu": [
            "标题：OpenAI、Google、Microsoft 都在做 Agent SDK，它们到底抽象了什么？",
            "用一张表比较 agents/tools/state/guardrails/tracing。",
            "强调会用框架不够，要能讲清 runtime 抽象。",
        ],
    },
    {
        "priority": "P0-06",
        "topic": "LangGraph / Stateful Agent Runtime",
        "learn_focus": "状态图、checkpoint、durable execution、human-in-the-loop、memory。",
        "interview_value": "生产级 Agent 和普通 while-loop 的分水岭。",
        "summary": "Stateful Agent Runtime 把 Agent 任务建模成可 checkpoint、可恢复、可插人工节点的状态图。",
        "core_architecture": [
            "Graph node 表示模型调用、工具调用、人工审批、写入等步骤。",
            "State 在节点之间流动，并通过 checkpoint 支持恢复。",
            "Conditional edge 根据状态决定下一步路径。",
        ],
        "key_modules": [
            "State schema：定义任务状态字段。",
            "Nodes：执行模型、工具或人工交互。",
            "Checkpoint：保存中间状态。",
            "Memory：保存跨任务或跨会话信息。",
        ],
        "engineering_implementation": [
            "把每日学习入库流程画成 graph：research -> filter -> write -> verify -> closeout。",
            "为 write 和 verify 节点增加失败恢复策略。",
            "把人工复核做成中断节点，而不是写在最后的文本里。",
        ],
        "interview_questions": [
            "为什么生产 Agent 需要 durable execution？",
            "checkpoint 保存什么，不应该保存什么？",
            "LangGraph 相比线性 chain 的优势是什么？",
        ],
        "mini_demo": [
            "用字典状态模拟 4 个节点。",
            "每个节点执行后写 checkpoint.json。",
            "故意让 verify 失败，再从 checkpoint 恢复。",
        ],
        "xiaohongshu": [
            "标题：生产级 Agent 为什么要有“存档点”？",
            "用游戏存档类比 checkpoint。",
            "展示一个状态图：检索、写作、校验、人工确认。",
        ],
    },
    {
        "priority": "P0-07",
        "topic": "Context Engineering",
        "learn_focus": "上下文预算、短期/长期记忆、压缩、摘要、retrieval、scratchpad。",
        "interview_value": "长任务 Agent、Codex 类工具、复杂业务 Agent 都会问。",
        "summary": "Context Engineering 是把有限上下文分配给目标、证据、状态、历史和工具结果的工程能力。",
        "core_architecture": [
            "短期上下文放当前任务目标、计划、最近工具结果。",
            "长期记忆放稳定偏好、项目背景和可复用事实。",
            "压缩层把长历史变成可验证摘要，并保留引用指针。",
        ],
        "key_modules": [
            "Context budgeter：决定每类内容占多少 token。",
            "Retriever：按任务取回相关证据。",
            "Compressor：压缩历史和工具结果。",
            "Scratchpad：保存推理过程中的工作状态。",
        ],
        "engineering_implementation": [
            "为 Obsidian 工作站定义 context pack：today、project、recent decisions、open tasks、relevant notes。",
            "每次任务只注入必要链接和摘要，不全量塞入笔记。",
            "把上下文压缩结果写入可复核的 context_snapshot.md。",
        ],
        "interview_questions": [
            "上下文窗口变大后，为什么仍然需要 context engineering？",
            "长期记忆和 RAG 有什么区别？",
            "摘要压缩会丢信息，如何降低风险？",
        ],
        "mini_demo": [
            "准备 10 篇项目笔记。",
            "写一个 context pack 选择器，输出 5 条最相关摘要和链接。",
            "比较全量输入与 context pack 输入的回答质量。",
        ],
        "xiaohongshu": [
            "标题：上下文窗口再大，也不能把所有东西都塞给 AI。",
            "用“开会材料包”解释 context pack。",
            "给出一个个人知识库的上下文模板。",
        ],
    },
    {
        "priority": "P0-08",
        "topic": "Tool Design for Agents",
        "learn_focus": "工具命名、schema、幂等性、权限、返回信息密度、错误处理。",
        "interview_value": "工具设计决定 Agent 成败，面试非常容易追问。",
        "summary": "好工具不是把 API 直接丢给模型，而是给 Agent 稳定、低歧义、可审计的动作边界。",
        "core_architecture": [
            "工具名表达意图，schema 限定输入，返回值服务下一步决策。",
            "工具按风险分级：只读、可写、外部副作用、需要审批。",
            "错误要结构化返回，让 Agent 能决定重试、降级或转人工。",
        ],
        "key_modules": [
            "Tool schema：参数、类型、约束、默认值。",
            "Permission policy：调用者、动作、资源、审批要求。",
            "Idempotency key：避免重复写入或重复扣费。",
            "Error contract：错误码、可重试性、恢复建议。",
        ],
        "engineering_implementation": [
            "把 write_note 设计为 upsert_note_draft 和 publish_note 两步。",
            "写入工具返回 diff、path、status，而不是长篇自然语言。",
            "为每个工具写 3 个失败样例，测试 Agent 是否能处理。",
        ],
        "interview_questions": [
            "为什么工具返回越详细不一定越好？",
            "Agent 工具如何设计幂等性？",
            "如何防止 prompt injection 诱导工具越权？",
        ],
        "mini_demo": [
            "设计 bad_tool 和 good_tool 两组 schema。",
            "用同一个任务比较模型调用稳定性。",
            "输出 tool_design_review.md。",
        ],
        "xiaohongshu": [
            "标题：AI Agent 经常翻车，不一定是模型差，可能是工具设计烂。",
            "对比“模糊工具”和“好工具 schema”。",
            "给出 5 条 Agent 工具设计 checklist。",
        ],
    },
    {
        "priority": "P0-09",
        "topic": "RAG 2.0 / Hybrid Retrieval",
        "learn_focus": "chunking、embedding、BM25、向量检索、rerank、metadata filter、引用。",
        "interview_value": "订单结构化、知识库、剧情理解都能用。",
        "summary": "RAG 2.0 不是只做向量检索，而是组合结构切块、关键词、向量、rerank、元数据过滤和引用校验。",
        "core_architecture": [
            "Ingestion 保留文档结构、来源、时间和权限元数据。",
            "Retrieval 同时使用 BM25、vector、metadata filter。",
            "Rerank 和 citation check 决定最终上下文是否可回答。",
        ],
        "key_modules": [
            "Chunker：结构切块、语义切块、表格/代码保护。",
            "Hybrid retriever：关键词与向量召回融合。",
            "Reranker：重排候选片段。",
            "Citation validator：检查答案是否被来源支持。",
        ],
        "engineering_implementation": [
            "先在本地 Markdown 上实现结构切块，不急着写 embedding。",
            "为每个 chunk 保存 heading_path、source_span、doc_type、updated_at。",
            "用复盘问题集评估 answerable@k 和 citation accuracy。",
        ],
        "interview_questions": [
            "为什么只用向量检索会漏掉精确字段？",
            "chunk 太大和太小分别有什么问题？",
            "如何评估 RAG 是否真的变好了？",
        ],
        "mini_demo": [
            "选 5 篇 Obsidian 笔记。",
            "实现 Markdown 标题级切块和关键词检索。",
            "用 10 个问题输出命中片段和引用。",
        ],
        "xiaohongshu": [
            "标题：知识库问答不是“丢进向量库”就完事了。",
            "画出 chunking -> hybrid retrieval -> rerank -> citation 的链路。",
            "用一个错误切块案例说明为什么要结构化。",
        ],
    },
    {
        "priority": "P0-10",
        "topic": "Agent / RAG Evaluation",
        "learn_focus": "golden set、trajectory eval、tool-call accuracy、faithfulness、context precision、CI regression。",
        "interview_value": "能证明系统“变好了”，是简历高级点。",
        "summary": "Evaluation 把 Agent/RAG 从“感觉可用”推进到“可回归、可比较、可上线”。",
        "core_architecture": [
            "Golden set 保存典型输入、期望行为、证据和评分标准。",
            "RAG eval 看 retrieval、context、answer 和 citation。",
            "Agent eval 还要看 trajectory、tool-call accuracy 和权限合规。",
        ],
        "key_modules": [
            "Dataset：问题、上下文、期望答案、禁用行为。",
            "Scorer：规则评分、LLM-as-judge、人工复核。",
            "Trace evaluator：检查工具调用顺序和状态变化。",
            "CI regression：每次改动前后对比指标。",
        ],
        "engineering_implementation": [
            "为个人工作站建立 20 条 golden questions。",
            "每条问题保存 expected_sources 和 failure_modes。",
            "把评测结果写入 05_Reviews/Project_Reviews。",
        ],
        "interview_questions": [
            "LLM-as-judge 有什么风险，如何校准？",
            "RAG 的 faithfulness 和 context precision 区别是什么？",
            "Agent 评测为什么不能只看最终答案？",
        ],
        "mini_demo": [
            "构建 10 条 RAG golden set。",
            "跑两种切块策略并比较 answerable@3。",
            "生成 eval_report.md。",
        ],
        "xiaohongshu": [
            "标题：怎么证明你的 AI 系统真的升级了？靠评测，不靠感觉。",
            "用考试卷类比 golden set。",
            "展示一个简单指标表。",
        ],
    },
    {
        "priority": "P0-11",
        "topic": "LLM Observability / Tracing",
        "learn_focus": "trace、span、token、latency、cost、tool call、retrieval hit、用户反馈。",
        "interview_value": "线上排障、AgentOps、LLMOps 必备。",
        "summary": "LLM Observability 让你能回答一次失败到底发生在检索、模型、工具、权限还是输出阶段。",
        "core_architecture": [
            "Trace 表示一次完整任务，span 表示模型调用、检索、工具调用等子步骤。",
            "每个 span 记录 latency、tokens、cost、error、input/output 摘要。",
            "用户反馈和评测结果回写到 trace，用于改进和排障。",
        ],
        "key_modules": [
            "Instrumentation：在模型、retriever、tool runtime 处打点。",
            "Trace store：保存结构化事件。",
            "Metrics：成功率、延迟、成本、工具失败率、召回命中率。",
            "Review UI：让人能从摘要跳到原始证据。",
        ],
        "engineering_implementation": [
            "为每日自动化生成 trace_id，并写入所有产物 frontmatter。",
            "把 token/cost 暂时留空，但先固定字段。",
            "Dashboard 展示最近失败、待复核、高成本任务。",
        ],
        "interview_questions": [
            "Trace 和普通日志有什么区别？",
            "LLM 应用最应该监控哪些指标？",
            "如何定位 RAG 回答错误的根因？",
        ],
        "mini_demo": [
            "用 JSONL 记录一次 RAG 查询的 retrieve、rerank、generate 三个 span。",
            "写一个 HTML 页面展示 timeline。",
            "手工标记一个失败原因。",
        ],
        "xiaohongshu": [
            "标题：AI 系统上线后，最怕的不是报错，而是不知道为什么错。",
            "用快递物流轨迹类比 trace。",
            "列出 LLMOps 必看的 6 个指标。",
        ],
    },
    {
        "priority": "P0-12",
        "topic": "Inference Serving / 成本优化",
        "learn_focus": "vLLM、PagedAttention、continuous batching、prefix cache、Ray Serve、autoscaling。",
        "interview_value": "AI Infra 岗位硬核内容。",
        "summary": "Inference Serving 的核心是在延迟、吞吐、显存和成本之间做工程权衡。",
        "core_architecture": [
            "Serving runtime 管理请求队列、KV cache、batching 和调度。",
            "Continuous batching 把不同时间到达的请求动态合批。",
            "Prefix cache 复用相同前缀上下文，降低重复计算。",
        ],
        "key_modules": [
            "Scheduler：请求排队、优先级和批处理。",
            "KV cache manager：显存分配、复用、淘汰。",
            "Autoscaler：按队列长度、延迟、GPU 利用率扩缩容。",
            "Router：多模型、多副本、多租户路由。",
        ],
        "engineering_implementation": [
            "为本地项目写一页 serving 架构图，解释 vLLM 和 Ray Serve 的位置。",
            "用模拟数据计算 QPS、p95 latency、GPU memory 的关系。",
            "把成本优化点写进简历项目：batching、cache、降级、小模型路由。",
        ],
        "interview_questions": [
            "PagedAttention 解决了什么问题？",
            "continuous batching 和普通 batching 有什么区别？",
            "如何为 LLM 服务设计 autoscaling 指标？",
        ],
        "mini_demo": [
            "不用真实 GPU，写一个请求队列模拟器。",
            "比较单请求处理、固定 batch、continuous batch 的吞吐。",
            "输出 latency/cost 小表格。",
        ],
        "xiaohongshu": [
            "标题：为什么同一个大模型，有的服务很贵有的很省？",
            "用餐厅翻台率类比 batching。",
            "解释 prefix cache 如何复用重复前缀。",
        ],
    },
    {
        "priority": "P0-13",
        "topic": "Agent Security / Guardrails",
        "learn_focus": "prompt injection、tool permission、sandbox、RBAC、audit、PII、human approval。",
        "interview_value": "toB 场景非常关键。",
        "summary": "Agent Security 的核心是默认不信任输入、限制工具权限、保留审计，并让高风险动作经过人审。",
        "core_architecture": [
            "输入层识别 prompt injection、PII、越权请求。",
            "执行层用 sandbox、RBAC 和审批控制工具调用。",
            "输出层做泄露检查、引用检查和策略校验。",
        ],
        "key_modules": [
            "Policy engine：定义允许/拒绝/需要审批。",
            "Sandbox：限制文件、网络、命令和外部副作用。",
            "PII scanner：识别敏感信息。",
            "Audit log：记录谁在何时通过什么工具访问什么资源。",
        ],
        "engineering_implementation": [
            "为 Obsidian 写入工具加审批字段和 diff 预览。",
            "把网络访问、文件删除、外部发布列为高风险动作。",
            "建立 prompt injection 测试样例，放入 eval 集。",
        ],
        "interview_questions": [
            "Prompt injection 和普通越权请求有什么区别？",
            "Agent 工具权限应该如何分层？",
            "如何在安全和可用性之间做权衡？",
        ],
        "mini_demo": [
            "设计 5 条恶意输入。",
            "写一个简单 policy checker。",
            "验证写入工具在高风险输入下进入 human approval。",
        ],
        "xiaohongshu": [
            "标题：让 AI 接工具前，先问一个问题：它能不能乱按按钮？",
            "用权限分层解释安全边界。",
            "列出个人项目也应该做的 5 个 guardrails。",
        ],
    },
    {
        "priority": "P0-14",
        "topic": "Structured Output / 信息抽取 Pipeline",
        "learn_focus": "JSON schema、字段校验、重试、置信度、人工复核、错误分类。",
        "interview_value": "直接包装你的 toB 多源订单结构化项目。",
        "summary": "结构化输出 Pipeline 的重点是把模型结果变成可校验、可重试、可人工复核的数据资产。",
        "core_architecture": [
            "Extraction prompt 只负责候选字段抽取。",
            "Schema validator 检查类型、必填、枚举、格式和业务约束。",
            "Repair/retry 层处理可修复错误，review queue 处理高风险样本。",
        ],
        "key_modules": [
            "JSON schema：定义字段和约束。",
            "Validator：校验格式和业务规则。",
            "Confidence scorer：标记低置信度字段。",
            "Human review：处理冲突、缺失和高价值订单。",
        ],
        "engineering_implementation": [
            "把订单抽取拆成 extract -> validate -> repair -> review -> export。",
            "每个字段保存 value、confidence、source_span。",
            "错误分类为 missing_field、format_error、conflict、low_confidence。",
        ],
        "interview_questions": [
            "结构化输出失败时你如何重试？",
            "为什么只靠 JSON mode 不够？",
            "人工复核队列应该按什么优先级排序？",
        ],
        "mini_demo": [
            "准备 10 条混乱订单文本。",
            "抽取成 JSON 后跑 schema 校验。",
            "生成 review_queue.csv。",
        ],
        "xiaohongshu": [
            "标题：AI 不是只能聊天，它还能把乱文本变成业务表格。",
            "展示原始文本 -> JSON -> 校验 -> 人审的流程。",
            "强调企业真正要的是稳定数据，不是漂亮回答。",
        ],
    },
    {
        "priority": "P0-15",
        "topic": "Multimodal Agent Pipeline",
        "learn_focus": "OCR、ASR、frame sampling、图文/视频 embedding、剧情事件抽取。",
        "interview_value": "直接服务短剧互动项目。",
        "summary": "多模态 Agent Pipeline 把视频、语音、画面和文本转成可检索、可推理、可交互的事件结构。",
        "core_architecture": [
            "采样层从视频抽帧、抽音频、切场景。",
            "理解层执行 OCR、ASR、视觉描述、人物/事件识别。",
            "结构化层生成 scene、character、event、emotion、choice point。",
        ],
        "key_modules": [
            "Frame sampler：按时间、镜头变化或事件抽帧。",
            "OCR/ASR：抽取字幕、台词、屏幕文字。",
            "Event extractor：识别剧情节点和互动机会。",
            "Retriever：按角色、情绪、事件检索片段。",
        ],
        "engineering_implementation": [
            "为短剧项目定义 scene_event.json schema。",
            "每个事件保存 timestamp、characters、dialogue、visual_cue、choice_opportunity。",
            "用小样本评估事件抽取是否支持互动分支设计。",
        ],
        "interview_questions": [
            "视频理解为什么不能只抽固定间隔帧？",
            "多模态 RAG 的索引对象是什么？",
            "如何评估剧情事件抽取质量？",
        ],
        "mini_demo": [
            "找一个 1 分钟视频样例。",
            "手工模拟 5 个 frame/ASR/OCR 输入。",
            "输出 scene_event.json 和一个互动选择点。",
        ],
        "xiaohongshu": [
            "标题：AI 怎么“看懂”一段短剧，并找出互动节点？",
            "拆成抽帧、识别、事件化、互动设计四步。",
            "用一张事件表展示结果。",
        ],
    },
]

MULTI_AGENT_WORKBENCH_FALLBACK_TOPICS = [
    {
        "priority": "Workbench-01",
        "topic": "Agent Memory Architecture",
        "summary": "Agent Memory Architecture 解决多 Agent 工作台里“每个 Agent 都只记得自己上下文，协作时背景断裂”的问题。",
        "learn_focus": "长期记忆、短期任务状态、共享工作区记忆、用户偏好和项目事实如何分层。",
        "interview_value": "能把多 Agent 系统从聊天编排讲到状态管理和知识沉淀，是工作台项目的核心架构点。",
        "workbench_problem": "多个 Agent 共同处理一个项目时，需要稳定记住用户偏好、项目约束、历史决策和当前任务状态，否则会重复提问、覆盖结论或互相打架。",
        "multi_agent_position": "位于 Agent Runtime 与 Artifact/Knowledge Store 之间，为 Planner、Research Agent、Writer Agent、Reviewer Agent 提供读写记忆的统一入口。",
        "data_model": [
            "memory_items(id, namespace, scope, type, content, source_ref, confidence, created_at, updated_at, expires_at)",
            "memory_links(id, from_memory_id, to_memory_id, relation, weight)",
            "memory_events(id, memory_id, action, actor_agent, reason, trace_id)",
        ],
        "api_design": [
            "POST /memory/write：写入事实、偏好、决策或任务状态。",
            "GET /memory/search?namespace=&scope=&query=：按项目/用户/任务检索记忆。",
            "POST /memory/consolidate：把短期上下文压缩为长期记忆候选。",
            "POST /memory/review：人工确认、拒绝或修改记忆。",
        ],
        "mini_demo": [
            "用 JSONL 建一个 memory_items 表。",
            "模拟 Research Agent 写入项目事实，Writer Agent 读取事实生成文档。",
            "让 Reviewer Agent 标记一条低置信度记忆为待复核。",
        ],
        "interview_questions": [
            "Agent memory 和普通 RAG 文档库有什么区别？",
            "哪些内容应该进长期记忆，哪些只应该留在 task state？",
            "如何避免错误记忆污染后续任务？",
        ],
        "resume_project": [
            "在简历中写：设计多 Agent 工作台记忆架构，支持 user/project/task 三层 namespace、记忆审计与人工复核。",
            "强调结果：减少重复上下文输入，使 Research/Writer/Reviewer Agent 能共享项目状态。",
        ],
    },
    {
        "priority": "Workbench-02",
        "topic": "Memory Write / Read / Forget Policy",
        "summary": "Memory Policy 决定 Agent 何时写、读、忘记记忆，避免系统既健忘又乱记。",
        "learn_focus": "写入门槛、读取排序、遗忘/过期、人工确认和错误回滚。",
        "interview_value": "能展示你理解 Agent memory 的治理问题，而不是只会做一个 vector store。",
        "workbench_problem": "没有策略时，Agent 会把临时猜测写成长期事实，或在不相关任务中读到旧上下文，导致回答漂移。",
        "multi_agent_position": "位于 Memory API 前的 policy 层，对所有 Agent 的 memory read/write/delete 请求做决策。",
        "data_model": [
            "memory_policy_rules(id, action, scope, condition, decision, requires_review)",
            "memory_access_logs(id, agent_id, action, memory_id, decision, reason, trace_id)",
            "memory_review_queue(id, memory_id, proposed_action, reviewer, status)",
        ],
        "api_design": [
            "POST /memory/policy/evaluate：输入 action、candidate memory、agent_id，返回 allow/review/deny。",
            "POST /memory/forget：软删除或过期记忆，并记录 reason。",
            "GET /memory/read-plan：返回本次任务允许读取的 memory scopes。",
        ],
        "mini_demo": [
            "写 5 条规则：用户偏好可长期写入，模型猜测必须待复核，任务临时状态 7 天过期。",
            "模拟 3 次写入请求，输出 allow/review/deny。",
            "生成 memory_access_logs.md 做审计。",
        ],
        "interview_questions": [
            "为什么 Agent memory 不能默认全自动写入？",
            "遗忘策略和数据安全有什么关系？",
            "如何处理已经被证明错误的长期记忆？",
        ],
        "resume_project": [
            "写成：实现 Memory Policy 层，支持写入准入、读取范围控制、过期遗忘和人工复核队列。",
            "项目亮点是把记忆从“存储功能”升级为可治理的 AgentOps 能力。",
        ],
    },
    {
        "priority": "Workbench-03",
        "topic": "Memory Scope / Namespace Design",
        "summary": "Memory Namespace 解决多项目、多用户、多 Agent 混用时的上下文污染问题。",
        "learn_focus": "user/project/task/agent/global 五类 scope，以及 namespace 继承和隔离。",
        "interview_value": "多 Agent 工作台非常容易被追问权限、租户隔离和项目上下文边界。",
        "workbench_problem": "如果所有记忆都在同一个池子里，A 项目的决策可能污染 B 项目，个人偏好也可能被当成团队规范。",
        "multi_agent_position": "位于 Memory Store、Tool Gateway、Policy Engine 共同使用的上下文边界层。",
        "data_model": [
            "namespaces(id, type, owner_id, parent_id, name, visibility)",
            "memory_items(namespace_id, scope, content, sensitivity, ttl)",
            "namespace_acl(namespace_id, principal_type, principal_id, permission)",
        ],
        "api_design": [
            "POST /namespaces：创建 user/project/task namespace。",
            "GET /namespaces/{id}/effective-context：解析继承后的可读上下文。",
            "POST /namespaces/{id}/acl：配置 Agent 或用户的访问权限。",
        ],
        "mini_demo": [
            "创建 user:me、project:workbench、task:daily-research 三层 namespace。",
            "写入 6 条记忆，验证 task 能读 project/user，不能读无关 project。",
            "输出 namespace_resolution.md。",
        ],
        "interview_questions": [
            "namespace 和 metadata filter 的区别是什么？",
            "如何处理跨项目共享知识？",
            "权限应该跟 memory item 绑定还是跟 namespace 绑定？",
        ],
        "resume_project": [
            "写成：设计多层 Memory Namespace 与 ACL，隔离用户偏好、项目事实和任务状态，降低跨任务上下文污染。",
        ],
    },
    {
        "priority": "Workbench-04",
        "topic": "Model Gateway / LLM Gateway",
        "summary": "Model Gateway 统一封装不同模型供应商、限流、日志、成本和降级策略。",
        "learn_focus": "provider adapter、统一请求格式、重试降级、成本记录、trace 注入。",
        "interview_value": "AI Infra/LLMOps 项目里非常硬的工程模块，可以解释多模型接入和成本控制。",
        "workbench_problem": "多 Agent 工作台里不同 Agent 可能需要不同模型，如果直接散落调用 SDK，会导致日志、成本、限流和故障处理不可控。",
        "multi_agent_position": "位于所有 Agent Runtime 与外部 LLM Provider 之间，是模型调用的统一入口。",
        "data_model": [
            "model_requests(id, trace_id, agent_id, provider, model, prompt_tokens, completion_tokens, cost, latency_ms, status)",
            "model_providers(id, name, base_url, auth_ref, enabled)",
            "model_policies(id, task_type, preferred_models, fallback_models, budget_limit)",
        ],
        "api_design": [
            "POST /llm/chat：统一 chat/completions 请求入口。",
            "POST /llm/responses：统一 response/tool-call 请求入口。",
            "GET /llm/usage?trace_id=：查询成本、token、延迟。",
            "POST /llm/route/preview：预览某任务会选哪个模型。",
        ],
        "mini_demo": [
            "写一个 fake gateway，支持 cheap_model 和 strong_model 两个模拟 provider。",
            "按 task_type 路由：总结走 cheap，代码审查走 strong。",
            "记录 model_requests.jsonl 并汇总成本。",
        ],
        "interview_questions": [
            "为什么需要 LLM Gateway，而不是在每个 Agent 里直接调用模型？",
            "如何做模型降级而不破坏输出格式？",
            "Gateway 如何支持 tracing 和成本核算？",
        ],
        "resume_project": [
            "写成：实现统一 LLM Gateway，抽象多供应商模型调用，支持路由、降级、成本统计和 trace 关联。",
        ],
    },
    {
        "priority": "Workbench-05",
        "topic": "Model Routing Strategy",
        "summary": "Model Routing Strategy 决定不同任务用哪个模型，平衡质量、成本、延迟和安全。",
        "learn_focus": "按任务类型、上下文长度、风险等级、预算和历史表现进行动态路由。",
        "interview_value": "能把“省钱”和“稳定”讲成算法和系统设计，而不是随便换模型。",
        "workbench_problem": "所有任务都用最强模型成本太高，全部用便宜模型又会影响复杂规划、代码和安全任务。",
        "multi_agent_position": "位于 Model Gateway 内部，接收 Agent 的 task profile，输出 selected_model 和 fallback plan。",
        "data_model": [
            "routing_rules(id, task_type, risk_level, max_latency_ms, max_cost, candidate_models)",
            "model_scorecards(model, task_type, quality_score, latency_p95, cost_per_1k, failure_rate)",
            "routing_decisions(id, trace_id, selected_model, reason, fallback_model)",
        ],
        "api_design": [
            "POST /llm/route：输入 task_profile，返回 selected_model。",
            "POST /llm/route/feedback：回写质量、延迟、失败结果。",
            "GET /llm/models/scorecard：查看模型表现。",
        ],
        "mini_demo": [
            "准备 10 个任务 profile：summarize、plan、code、review、extract。",
            "用规则路由到 fast/cheap/strong 三个模拟模型。",
            "输出 routing_decisions.md，解释每次选择理由。",
        ],
        "interview_questions": [
            "模型路由如何评估质量？",
            "什么场景应该优先低延迟，什么场景优先高质量？",
            "路由策略如何避免频繁抖动？",
        ],
        "resume_project": [
            "写成：设计模型路由策略，根据任务类型、风险和预算动态选择模型，并记录 routing decision 用于回归评估。",
        ],
    },
    {
        "priority": "Workbench-06",
        "topic": "Tool Gateway / Capability Gateway",
        "summary": "Tool Gateway 把所有工具能力统一注册、鉴权、限流、审计，避免 Agent 直接接触危险接口。",
        "learn_focus": "工具 schema、权限、幂等、审计、返回值压缩和错误契约。",
        "interview_value": "工具治理是 AgentOps 高频点，能体现你知道 Agent 真正翻车的位置。",
        "workbench_problem": "多个 Agent 共用文件、搜索、写入、部署等工具时，如果没有统一网关，权限和日志会散落在各个 Agent 里。",
        "multi_agent_position": "位于 Agent Runtime 与外部系统/API/MCP server 之间，是所有 tool call 的控制平面。",
        "data_model": [
            "capabilities(id, name, schema, risk_level, owner, enabled)",
            "tool_invocations(id, trace_id, agent_id, capability_id, args_hash, status, latency_ms)",
            "tool_permissions(capability_id, principal_id, permission, requires_approval)",
        ],
        "api_design": [
            "GET /capabilities：列出当前 Agent 可用工具。",
            "POST /tools/invoke：统一工具调用入口。",
            "POST /tools/validate：调用前校验 schema 和权限。",
            "GET /tools/invocations/{trace_id}：查看工具调用日志。",
        ],
        "mini_demo": [
            "定义 search_notes、write_draft、publish_note 三个 capability。",
            "让 Writer Agent 只能 write_draft，不能 publish_note。",
            "输出 tool_invocations.jsonl 展示审批拦截。",
        ],
        "interview_questions": [
            "Tool Gateway 和 MCP server 的关系是什么？",
            "工具权限应该按 Agent、用户还是任务配置？",
            "如何设计工具返回值，让模型既够用又不爆上下文？",
        ],
        "resume_project": [
            "写成：实现 Tool/Capability Gateway，统一管理 Agent 工具 schema、权限、审计与审批。",
        ],
    },
    {
        "priority": "Workbench-07",
        "topic": "Agent Registry / Capability Registry",
        "summary": "Agent Registry 让工作台知道有哪些 Agent、能做什么、何时可用、如何委托。",
        "learn_focus": "Agent Card、能力标签、版本、健康状态、输入输出契约。",
        "interview_value": "是多 Agent 从硬编码函数调用走向平台化调度的关键。",
        "workbench_problem": "没有 registry 时，Orchestrator 只能硬编码调用固定 Agent，无法发现新能力或按任务动态委托。",
        "multi_agent_position": "位于 Orchestrator/Planner 旁边，提供 Agent discovery 和 capability lookup。",
        "data_model": [
            "agents(id, name, version, status, endpoint, owner)",
            "agent_capabilities(agent_id, capability, input_schema, output_schema, risk_level)",
            "agent_health(agent_id, last_seen_at, success_rate, latency_p95)",
        ],
        "api_design": [
            "POST /agents/register：注册 Agent Card。",
            "GET /agents/search?capability=：按能力查找 Agent。",
            "GET /agents/{id}/health：查看健康与性能。",
            "POST /agents/{id}/deprecate：下线旧版本。",
        ],
        "mini_demo": [
            "注册 Research、Writer、Reviewer 三个 Agent。",
            "Planner 根据 capability=review 自动选择 Reviewer。",
            "模拟一个 Agent unhealthy 后切换到备用 Agent。",
        ],
        "interview_questions": [
            "Agent Registry 和服务发现有什么区别？",
            "如何描述一个 Agent 的能力边界？",
            "多版本 Agent 如何灰度？",
        ],
        "resume_project": [
            "写成：设计 Agent/Capability Registry，支持 Agent 能力发现、版本管理和健康状态路由。",
        ],
    },
    {
        "priority": "Workbench-08",
        "topic": "Concurrent Agent Execution",
        "summary": "Concurrent Execution 让多个 Agent 并发工作，同时避免共享状态冲突和资源打爆。",
        "learn_focus": "并发任务拆分、join、锁、状态隔离、超时和取消。",
        "interview_value": "能解释多 Agent 系统为什么不是简单开多个线程。",
        "workbench_problem": "Research、Code、Review 等 Agent 可以并行，但它们可能同时写 artifact 或抢同一模型/工具资源。",
        "multi_agent_position": "位于 Orchestrator 的 execution engine 中，负责 fan-out/fan-in 和并发控制。",
        "data_model": [
            "runs(id, goal, status, started_at, ended_at)",
            "agent_tasks(id, run_id, agent_id, dependency_ids, status, timeout_ms)",
            "locks(resource_id, holder_task_id, expires_at)",
        ],
        "api_design": [
            "POST /runs/{id}/tasks：创建并发任务。",
            "POST /tasks/{id}/cancel：取消任务。",
            "POST /locks/acquire：申请共享资源锁。",
            "GET /runs/{id}/join：等待并汇总并发结果。",
        ],
        "mini_demo": [
            "让 Research Agent 和 Example Agent 并发生成资料和 demo。",
            "Reviewer Agent 等两者完成后再执行。",
            "用 tasks.jsonl 展示 fan-out/fan-in。",
        ],
        "interview_questions": [
            "并发 Agent 如何处理共享 artifact 写冲突？",
            "什么时候并发会降低质量？",
            "如何设计超时和取消？",
        ],
        "resume_project": [
            "写成：实现多 Agent 并发执行引擎，支持任务依赖、fan-out/fan-in、超时取消与共享资源锁。",
        ],
    },
    {
        "priority": "Workbench-09",
        "topic": "Backpressure / Queue / Rate Limit",
        "summary": "Backpressure 让工作台在请求过多、模型限流或工具慢的时候稳定降速而不是崩溃。",
        "learn_focus": "队列、优先级、令牌桶、重试退避、降级和拒绝策略。",
        "interview_value": "AI Infra 面试会非常看重你是否理解真实服务的流量控制。",
        "workbench_problem": "多个 Agent 同时调用模型和工具时，容易撞上 provider rate limit、队列堆积和成本失控。",
        "multi_agent_position": "位于 Model Gateway、Tool Gateway 和 Execution Engine 的入口处。",
        "data_model": [
            "queues(id, name, priority_policy, max_depth)",
            "queued_jobs(id, queue_id, run_id, priority, status, attempts, next_retry_at)",
            "rate_limits(scope, limit, window_seconds, used, reset_at)",
        ],
        "api_design": [
            "POST /queues/enqueue：提交任务。",
            "GET /queues/{id}/metrics：查看深度、延迟、失败率。",
            "POST /rate-limit/check：调用前检查配额。",
            "POST /jobs/{id}/retry：按退避策略重试。",
        ],
        "mini_demo": [
            "用令牌桶模拟每分钟 5 次模型调用限制。",
            "提交 12 个 Agent task，观察排队、延迟和拒绝。",
            "输出 queue_metrics.md。",
        ],
        "interview_questions": [
            "Backpressure 和 retry 有什么区别？",
            "队列满了应该丢弃、降级还是阻塞？",
            "如何避免重试风暴？",
        ],
        "resume_project": [
            "写成：实现 Agent 任务队列与 rate limit 控制，支持优先级、退避重试和限流降级。",
        ],
    },
    {
        "priority": "Workbench-10",
        "topic": "Durable Workflow / Long-running Task",
        "summary": "Durable Workflow 让长时间 Agent 任务能暂停、恢复、重试和跨天继续。",
        "learn_focus": "workflow state、checkpoint、activity、timer、resume token。",
        "interview_value": "长任务 Agent 是生产系统分水岭，尤其适合工作台项目表达。",
        "workbench_problem": "复杂研究、代码生成、文档整理可能运行很久，中途失败或人工等待时不能丢状态。",
        "multi_agent_position": "位于 Orchestrator 的 workflow runtime，管理跨 Agent、跨工具、跨时间的执行状态。",
        "data_model": [
            "workflows(id, type, status, current_step, state_json, created_at, updated_at)",
            "workflow_steps(id, workflow_id, name, status, input_json, output_json, attempts)",
            "checkpoints(id, workflow_id, step_id, state_snapshot, created_at)",
        ],
        "api_design": [
            "POST /workflows/start：启动长任务。",
            "POST /workflows/{id}/checkpoint：保存状态。",
            "POST /workflows/{id}/resume：从 checkpoint 恢复。",
            "POST /workflows/{id}/signal：接收人工审批或外部事件。",
        ],
        "mini_demo": [
            "模拟 research -> write -> approval -> publish 四步工作流。",
            "在 approval 处暂停，把 checkpoint 写到 JSON。",
            "手工 signal approve 后恢复执行。",
        ],
        "interview_questions": [
            "durable workflow 和普通 cron job 有什么区别？",
            "checkpoint 应该保存哪些状态？",
            "如何处理长任务里的人工审批？",
        ],
        "resume_project": [
            "写成：设计 Durable Agent Workflow，支持 checkpoint、人工 signal、失败恢复和跨天任务继续执行。",
        ],
    },
    {
        "priority": "Workbench-11",
        "topic": "Idempotency / Dedup",
        "summary": "Idempotency 让 Agent 重试或恢复时不会重复写入、重复扣费或重复发布。",
        "learn_focus": "idempotency key、请求去重、结果缓存、副作用保护。",
        "interview_value": "这是很多 Agent demo 变生产系统时必补的可靠性能力。",
        "workbench_problem": "Agent 失败后重试 write/publish/payment/tool call，可能产生重复笔记、重复审批或重复外部操作。",
        "multi_agent_position": "位于 Tool Gateway、Artifact Store 和 Workflow Runtime 的副作用边界。",
        "data_model": [
            "idempotency_keys(key, scope, request_hash, response_ref, status, expires_at)",
            "dedup_events(id, key, action, decision, trace_id)",
            "side_effects(id, tool_name, target_ref, idempotency_key, status)",
        ],
        "api_design": [
            "POST /idempotency/check：检查 key 是否已执行。",
            "POST /tools/invoke 带 Idempotency-Key header。",
            "GET /side-effects?trace_id=：查看副作用执行记录。",
        ],
        "mini_demo": [
            "模拟 publish_note 工具调用两次，使用同一个 idempotency_key。",
            "第一次创建 artifact，第二次直接返回已有结果。",
            "输出 dedup_events.md。",
        ],
        "interview_questions": [
            "幂等和去重有什么区别？",
            "idempotency key 应该由客户端生成还是服务端生成？",
            "如何处理同 key 但请求体不同的情况？",
        ],
        "resume_project": [
            "写成：为 Agent 工具副作用设计 idempotency/dedup 机制，避免重试导致重复写入和重复发布。",
        ],
    },
    {
        "priority": "Workbench-12",
        "topic": "Event Bus / Agent Event Stream",
        "summary": "Event Stream 把 Agent 的计划、工具、状态和产物变成可订阅的事件流。",
        "learn_focus": "事件模型、pub/sub、SSE/WebSocket、trace event、状态聚合。",
        "interview_value": "它连接后端 AgentOps 和前端可视化，是工作台体验的骨架。",
        "workbench_problem": "没有事件流，前端只能等最终结果，无法展示过程、审批、失败位置和中间产物。",
        "multi_agent_position": "位于 Agent Runtime、Workflow、UI Dashboard、Observability 之间的消息层。",
        "data_model": [
            "agent_events(id, run_id, agent_id, type, payload_json, sequence, created_at)",
            "subscriptions(id, run_id, subscriber, filter, cursor)",
            "event_offsets(run_id, consumer, last_sequence)",
        ],
        "api_design": [
            "POST /events：写入事件。",
            "GET /events/stream?run_id=：通过 SSE 订阅事件。",
            "GET /events?cursor=：断线后补拉。",
            "POST /events/reduce：把事件折叠成当前状态。",
        ],
        "mini_demo": [
            "生成 plan_started、tool_called、artifact_ready、approval_required 四类事件。",
            "写一个静态 HTML 轮询 events.jsonl 展示 timeline。",
            "模拟断点续读 cursor。",
        ],
        "interview_questions": [
            "事件流和数据库状态表为什么都需要？",
            "SSE 和 WebSocket 如何选择？",
            "如何保证事件顺序和断线恢复？",
        ],
        "resume_project": [
            "写成：设计 Agent Event Stream，支持多 Agent 执行过程可视化、断点续读和 trace timeline。",
        ],
    },
    {
        "priority": "Workbench-13",
        "topic": "Global State / Shared Workspace State",
        "summary": "Shared Workspace State 让多个 Agent 对同一任务空间形成一致视图。",
        "learn_focus": "run state、workspace state、锁、版本号、冲突合并。",
        "interview_value": "多 Agent 协作不是只看消息，还要有共享状态与一致性策略。",
        "workbench_problem": "多个 Agent 同时修改任务计划、artifact 状态或项目进度时，容易互相覆盖。",
        "multi_agent_position": "位于 Orchestrator 和各 Agent 之间，作为 run/workspace 的权威状态源。",
        "data_model": [
            "workspace_states(workspace_id, version, state_json, updated_by, updated_at)",
            "state_patches(id, workspace_id, base_version, patch_json, status)",
            "state_conflicts(id, workspace_id, patch_id, reason, resolution)",
        ],
        "api_design": [
            "GET /workspace-state/{id}：读取当前状态和 version。",
            "PATCH /workspace-state/{id}：带 base_version 提交状态变更。",
            "POST /workspace-state/{id}/resolve-conflict：解决冲突。",
        ],
        "mini_demo": [
            "Research Agent 和 Writer Agent 同时提交 state patch。",
            "用 version 检测冲突。",
            "手工合并后输出 state_history.md。",
        ],
        "interview_questions": [
            "共享状态和事件日志的关系是什么？",
            "多 Agent 状态冲突如何解决？",
            "什么时候需要强一致，什么时候最终一致即可？",
        ],
        "resume_project": [
            "写成：实现 Shared Workspace State，支持版本化 state patch、冲突检测和多 Agent 协作一致性。",
        ],
    },
    {
        "priority": "Workbench-14",
        "topic": "Artifact Store",
        "summary": "Artifact Store 统一管理 Agent 生成的文档、代码、表格、图表和中间产物。",
        "learn_focus": "artifact metadata、版本、血缘、权限、预览和引用。",
        "interview_value": "能把 Agent 输出从聊天文本升级为可管理的工程产物。",
        "workbench_problem": "没有 artifact store，Agent 产物散落在消息里，无法版本管理、复用、回滚或审计。",
        "multi_agent_position": "位于 Agent Runtime、Review UI、Knowledge Base 和 Project Workspace 之间。",
        "data_model": [
            "artifacts(id, type, path, title, owner_agent, run_id, version, status)",
            "artifact_versions(id, artifact_id, version, content_hash, created_at)",
            "artifact_links(id, artifact_id, source_trace_id, source_memory_id)",
        ],
        "api_design": [
            "POST /artifacts：创建 artifact。",
            "GET /artifacts/{id}/versions：查看版本。",
            "POST /artifacts/{id}/promote：从 draft 变成 reviewed/published。",
            "GET /artifacts/search：按 run、project、type 检索。",
        ],
        "mini_demo": [
            "让 Writer Agent 生成 draft.md。",
            "Reviewer Agent 生成 review.patch。",
            "Artifact Store 保存两个版本并输出 artifact_index.md。",
        ],
        "interview_questions": [
            "Artifact 和普通文件有什么区别？",
            "如何追踪一个产物来自哪些工具和上下文？",
            "如何做 artifact 的版本回滚？",
        ],
        "resume_project": [
            "写成：设计 Artifact Store，管理 Agent 生成产物的版本、血缘、状态和项目索引。",
        ],
    },
    {
        "priority": "Workbench-15",
        "topic": "Run Replay / Time-travel Debugging",
        "summary": "Run Replay 让你重放一次 Agent 运行，定位失败来自模型、工具、状态还是策略。",
        "learn_focus": "trace snapshot、event sourcing、tool mock、deterministic replay、diff。",
        "interview_value": "这是 AgentOps 高阶能力，能证明你会做可调试系统。",
        "workbench_problem": "Agent 失败后只看最终回答很难定位原因；需要重放当时的输入、工具结果和状态。",
        "multi_agent_position": "位于 Observability、Workflow Runtime、Tool Gateway 之间，用于调试和回归。",
        "data_model": [
            "run_snapshots(run_id, input_snapshot, state_snapshot, config_snapshot, created_at)",
            "replay_runs(id, source_run_id, mode, status, diff_summary)",
            "tool_mocks(id, run_id, tool_name, request_hash, response_json)",
        ],
        "api_design": [
            "POST /runs/{id}/snapshot：保存可重放快照。",
            "POST /runs/{id}/replay：使用 mock tool 重放。",
            "GET /replays/{id}/diff：查看 replay 与原 run 的差异。",
        ],
        "mini_demo": [
            "保存一次 Agent run 的 events 和 tool responses。",
            "修改 prompt 后重放同一 run。",
            "输出 replay_diff.md 比较工具调用和最终产物差异。",
        ],
        "interview_questions": [
            "为什么 Agent replay 很难做到完全确定性？",
            "哪些内容必须进入 snapshot？",
            "tool mock 对回归测试有什么价值？",
        ],
        "resume_project": [
            "写成：实现 Run Replay 与 trace diff，用于多 Agent 工作流失败定位和 prompt/model 升级回归。",
        ],
    },
    {
        "priority": "Workbench-16",
        "topic": "Prompt / Agent Config Registry",
        "summary": "Config Registry 管理 prompt、工具列表、模型、策略和版本，避免 Agent 配置散落不可复现。",
        "learn_focus": "配置版本、灰度、回滚、prompt diff、环境隔离。",
        "interview_value": "能解释 prompt 工程如何进入软件工程生命周期。",
        "workbench_problem": "Agent prompt 和工具配置随手改后，线上行为变了但无法复现，也不知道哪个版本引入问题。",
        "multi_agent_position": "位于 Agent Registry 和 Runtime 启动流程之间，提供版本化配置。",
        "data_model": [
            "agent_configs(id, agent_id, version, model, prompt_ref, toolset_ref, policy_ref, status)",
            "prompts(id, name, version, content, variables, checksum)",
            "config_deployments(id, config_id, environment, rollout_percent, status)",
        ],
        "api_design": [
            "POST /configs：创建 Agent 配置版本。",
            "GET /configs/{agent_id}/active：获取当前生效配置。",
            "POST /configs/{id}/rollback：回滚版本。",
            "GET /prompts/{id}/diff?base=：比较 prompt 差异。",
        ],
        "mini_demo": [
            "为 Reviewer Agent 创建 v1/v2 两个 prompt。",
            "用同一条输入比较输出差异。",
            "生成 prompt_diff.md。",
        ],
        "interview_questions": [
            "Prompt 版本管理和代码版本管理有什么不同？",
            "如何灰度发布一个新 Agent 配置？",
            "配置回滚需要保留哪些依赖？",
        ],
        "resume_project": [
            "写成：设计 Prompt/Agent Config Registry，支持版本化、灰度、diff 与回滚，提升 Agent 行为可复现性。",
        ],
    },
    {
        "priority": "Workbench-17",
        "topic": "Policy Engine / Permission as Code",
        "summary": "Policy Engine 把 Agent 权限、安全和审批规则写成可测试、可审计的策略。",
        "learn_focus": "allow/deny/review、RBAC/ABAC、资源策略、策略测试。",
        "interview_value": "toB Agent 工作台一定会问权限和安全，Permission as Code 很加分。",
        "workbench_problem": "权限散落在工具代码和 prompt 里不可审计，Agent 一旦接触写入、发布、外部 API 就有风险。",
        "multi_agent_position": "横切 Model Gateway、Tool Gateway、Memory、Artifact Store、Human Approval。",
        "data_model": [
            "policies(id, name, version, resource, action, condition, effect)",
            "policy_decisions(id, trace_id, principal, action, resource, decision, reason)",
            "policy_tests(id, policy_id, input_json, expected_decision)",
        ],
        "api_design": [
            "POST /policy/evaluate：返回 allow/deny/review。",
            "POST /policy/test：运行策略测试集。",
            "GET /policy/decisions?trace_id=：查询策略判定。",
        ],
        "mini_demo": [
            "写 5 条策略：只读允许，写入草稿允许，发布需要审批，删除拒绝。",
            "用 8 个 tool call 请求跑 policy test。",
            "输出 policy_decisions.md。",
        ],
        "interview_questions": [
            "RBAC 和 ABAC 在 Agent 权限里如何选择？",
            "为什么策略要可测试？",
            "Prompt injection 如何触发 policy review？",
        ],
        "resume_project": [
            "写成：实现 Permission-as-Code Policy Engine，统一控制 Agent 工具、记忆和产物权限，并记录审计决策。",
        ],
    },
    {
        "priority": "Workbench-18",
        "topic": "Human Task Queue / Approval Center",
        "summary": "Approval Center 把需要人判断的 Agent 动作变成可排队、可处理、可审计的任务。",
        "learn_focus": "审批任务、优先级、SLA、diff 预览、结果回写。",
        "interview_value": "Human-in-the-loop 是企业 Agent 落地关键，不是 UI 上放个确认按钮那么简单。",
        "workbench_problem": "高风险写入、发布、删除、记忆固化都需要人审；如果没有队列，审批会散落在聊天上下文里。",
        "multi_agent_position": "连接 Policy Engine、Workflow Runtime、前端管理台和 Artifact Store。",
        "data_model": [
            "human_tasks(id, run_id, type, title, payload_ref, priority, assignee, status, due_at)",
            "approval_decisions(id, task_id, decision, comment, decided_by, decided_at)",
            "approval_callbacks(task_id, workflow_id, resume_signal)",
        ],
        "api_design": [
            "POST /human-tasks：创建审批任务。",
            "GET /human-tasks?status=pending：拉取待办。",
            "POST /human-tasks/{id}/decide：批准、拒绝或要求修改。",
            "POST /workflows/{id}/signal：把审批结果回写长任务。",
        ],
        "mini_demo": [
            "让 publish_note 触发 approval task。",
            "人工在 JSON 中写 approve/reject。",
            "workflow 读取决定后继续或停止。",
        ],
        "interview_questions": [
            "哪些 Agent 动作必须进入人工审批？",
            "审批任务如何和长任务恢复关联？",
            "如何避免审批中心变成瓶颈？",
        ],
        "resume_project": [
            "写成：设计 Human Approval Center，支持高风险 Agent 动作排队、diff 预览、审批回写和审计。",
        ],
    },
    {
        "priority": "Workbench-19",
        "topic": "Sandbox Execution Pool",
        "summary": "Sandbox Pool 让代码执行、文件操作和外部命令在隔离资源中运行，降低 Agent 工具风险。",
        "learn_focus": "隔离、资源配额、文件系统权限、网络权限、生命周期回收。",
        "interview_value": "Codex/Agent 类产品都会涉及 sandbox，是安全与工程能力交汇点。",
        "workbench_problem": "Agent 需要执行代码或命令来验证结果，但直接在宿主环境执行会带来数据泄露和破坏风险。",
        "multi_agent_position": "位于 Tool Gateway 的高风险执行后端，为 Code Agent、Test Agent、Data Agent 提供隔离运行环境。",
        "data_model": [
            "sandboxes(id, status, image, cpu_limit, memory_limit, network_policy, created_at)",
            "sandbox_jobs(id, sandbox_id, command_ref, status, stdout_ref, stderr_ref, exit_code)",
            "sandbox_mounts(sandbox_id, host_path, mode, allow_write)",
        ],
        "api_design": [
            "POST /sandboxes/acquire：申请隔离环境。",
            "POST /sandboxes/{id}/exec：执行命令。",
            "GET /sandbox-jobs/{id}/logs：读取日志。",
            "POST /sandboxes/{id}/release：释放资源。",
        ],
        "mini_demo": [
            "不用真实容器，先用临时目录模拟 sandbox。",
            "限制只允许写 tmp/workspace。",
            "执行一个测试命令并保存 stdout/stderr。",
        ],
        "interview_questions": [
            "Sandbox 要隔离哪些资源？",
            "如何控制 Agent 的网络访问？",
            "执行池如何回收异常任务？",
        ],
        "resume_project": [
            "写成：设计 Sandbox Execution Pool，为 Agent 代码执行提供文件、网络和资源隔离，并记录执行日志。",
        ],
    },
    {
        "priority": "Workbench-20",
        "topic": "Cost Metering / Budget Control",
        "summary": "Cost Metering 让工作台知道每个用户、项目、Agent、任务花了多少 token、模型成本和工具成本。",
        "learn_focus": "成本归因、预算上限、预估、告警、降级。",
        "interview_value": "LLMOps 里成本治理非常现实，能体现你考虑上线后的运营问题。",
        "workbench_problem": "多 Agent 并发和长任务很容易悄悄烧掉预算；没有归因就不知道哪个 Agent 或工作流最贵。",
        "multi_agent_position": "横切 Model Gateway、Tool Gateway、Workflow Runtime、Dashboard。",
        "data_model": [
            "usage_records(id, trace_id, project_id, agent_id, provider, model, tokens, cost, created_at)",
            "budgets(scope, scope_id, period, limit_amount, used_amount, alert_threshold)",
            "budget_events(id, budget_id, event_type, amount, action_taken)",
        ],
        "api_design": [
            "POST /usage/record：记录一次模型或工具成本。",
            "GET /usage/summary?project_id=：查看成本汇总。",
            "POST /budget/check：任务执行前检查预算。",
            "POST /budget/action：触发降级、暂停或人工确认。",
        ],
        "mini_demo": [
            "模拟 3 个 Agent 各调用 5 次模型。",
            "按 token 和模型单价计算 cost。",
            "预算超过阈值后把 strong_model 路由降级到 cheap_model。",
        ],
        "interview_questions": [
            "LLM 成本应该按用户、项目还是 run 归因？",
            "预算超限时应该拒绝、降级还是请求审批？",
            "如何预估一个长任务的成本？",
        ],
        "resume_project": [
            "写成：实现 Cost Metering 与 Budget Control，支持按项目/Agent 归因 token 成本、预算告警和模型降级。",
        ],
    },
]


JOB_MARKET_FALLBACK_TOPICS = [
    {
        "priority": "Job-P0-01",
        "topic": "Python Backend / Agent API",
        "summary": "Agent 最终要变成可调用、可观测、可测试的后端服务，而不是停留在 notebook 或聊天窗口里。",
        "learn_focus": "FastAPI、Pydantic、异步请求、错误处理、日志、run_id 和结构化响应。",
        "interview_value": "岗位会把 Agent 当生产服务考察，能讲清 API 边界比只会 prompt 更有区分度。",
        "workbench_problem": "多 Agent 工作台需要一个稳定入口接收任务、创建 run、返回状态和串起 trace，否则每个 Agent 都只是孤立脚本。",
        "multi_agent_position": "位于前端/CLI 与 Orchestrator 之间，是所有 Agent run 的统一服务入口。",
        "data_model": [
            "agent_runs(id, user_id, project_id, input, status, created_at, completed_at)",
            "run_steps(id, run_id, agent_id, step_type, status, latency_ms, error_code)",
            "api_errors(id, run_id, code, message, retryable, created_at)",
        ],
        "api_design": [
            "POST /agent/runs：创建一次 Agent run，返回 run_id。",
            "GET /agent/runs/{run_id}：查询状态、步骤和最终产物。",
            "POST /agent/runs/{run_id}/cancel：取消长任务。",
            "GET /agent/runs/{run_id}/events：流式返回状态和 trace 事件。",
        ],
        "core_architecture": [
            "API Layer 负责鉴权、参数校验、幂等 key 和响应格式。",
            "Orchestrator Adapter 把 HTTP 请求转换成内部 workflow/run。",
            "Trace Middleware 给每次请求注入 run_id、trace_id 和 request_id。",
            "Error Boundary 把模型、工具、状态机错误统一映射为可处理错误码。",
        ],
        "key_modules": [
            "FastAPI endpoint：提供同步提交、异步查询和事件流。",
            "Pydantic schema：约束输入任务、工具参数和结构化输出。",
            "Run repository：持久化 run、step、error 和 artifact 引用。",
            "Logging middleware：记录 latency、status、error_type 和 request size。",
        ],
        "engineering_implementation": [
            "先写 /agent/runs 和 /agent/runs/{id} 两个接口，用本地 JSONL 或 SQLite 存 run。",
            "每次请求生成 run_id 和 trace_id，并把后续 tool call、model call、memory call 都挂上去。",
            "所有响应都用 Pydantic 模型返回，不让自然语言直接进入下游系统。",
            "给 timeout、validation_error、tool_error、model_error 设计稳定错误码。",
        ],
        "mini_demo": [
            "用 FastAPI 写 /agent/run，输入 user_task，输出 run_id、status、structured_result。",
            "用 Pydantic 校验 user_task、priority、project_id。",
            "把每次运行写入 agent_runs.jsonl，并输出 latency_ms。",
        ],
        "interview_questions": [
            "为什么 Agent 原型需要封装成后端 API？",
            "Pydantic 在 Agent 工具调用和结构化输出里起什么作用？",
            "Agent API 如何处理长任务、超时和取消？",
        ],
        "resume_project": [
            "写成：基于 FastAPI/Pydantic 实现 Agent 服务入口，支持 run_id 状态查询、结构化输出、错误码和 trace 日志。",
        ],
        "xiaohongshu": [
            "标题：Agent 不是聊天框，最后一定要变成 API。",
            "用外卖系统类比：下单接口、订单号、状态查询、异常退款，对应 Agent run、run_id、trace 和 error code。",
            "强调工程感：能被前端、任务队列和监控系统调用，才是可上线的 Agent。",
        ],
        "validation_plan": [
            "用 5 个 mock user_task 调 /agent/run，确认都返回 run_id。",
            "传入缺字段请求，确认 Pydantic 返回稳定 validation error。",
            "模拟一次 tool_error，确认 run 状态变成 failed 且 error_code 可查询。",
        ],
    },
    {
        "priority": "Job-P0-02",
        "topic": "Tool Calling / Structured Output",
        "summary": "Tool Calling 和 Structured Output 是 Agent 从“会说”变成“能执行”的核心接口层。",
        "learn_focus": "JSON Schema、Pydantic 参数校验、工具选择、失败重试、结构化返回和审计日志。",
        "interview_value": "岗位高频要求 tool/function calling、structured output、Pydantic 和 JSON Schema，是最该先补的硬技能。",
        "workbench_problem": "工作台里的 Agent 需要安全调用搜索、写文件、创建任务、审批等工具；没有 schema 和结构化输出就无法稳定串流程。",
        "multi_agent_position": "位于 Agent Runtime 与 Tool Gateway 之间，负责把模型意图转换为可验证的工具调用。",
        "data_model": [
            "tool_schemas(id, name, version, json_schema, risk_level)",
            "tool_calls(id, run_id, agent_id, tool_name, args_json, status, error_code)",
            "structured_outputs(id, run_id, schema_name, payload_json, validation_status)",
        ],
        "api_design": [
            "POST /tools/validate：校验工具名、参数和权限。",
            "POST /tools/call：执行工具并返回结构化结果。",
            "POST /outputs/validate：校验模型输出是否符合 schema。",
        ],
        "core_architecture": [
            "Schema Registry 保存工具输入输出契约。",
            "Tool Selector 接收模型给出的 tool_call。",
            "Validator 在执行前做类型、必填项和权限校验。",
            "Retry Handler 根据错误类型决定重试、降级或人工确认。",
        ],
        "key_modules": [
            "Pydantic models：定义工具参数和最终输出。",
            "Tool executor：隔离真实函数调用与模型输出。",
            "Result normalizer：把工具返回压缩成模型可读、程序可解析的结构。",
            "Audit logger：记录 args_hash、result_status 和 latency。",
        ],
        "engineering_implementation": [
            "先定义 3 个 mock tools：search_docs、create_task、write_record。",
            "每个工具只暴露少量强类型参数，避免一个万能 data 字段。",
            "工具调用前做 schema 校验，调用后把结果转换成统一 ToolResult。",
            "失败分 timeout、validation_error、permission_denied、tool_exception 四类处理。",
        ],
        "mini_demo": [
            "用户输入任务后，模型或规则选择一个工具。",
            "用 Pydantic 校验工具参数。",
            "执行 mock Python 函数并记录 tool_calls.jsonl。",
            "输出结构化 JSON，包含 status、data、error。",
        ],
        "interview_questions": [
            "Function calling 的执行链路是什么？",
            "怎么设计一个不容易被模型误用的 tool schema？",
            "Structured output 和普通自然语言输出有什么工程差异？",
        ],
        "resume_project": [
            "写成：设计 Agent 工具调用层，使用 JSON Schema/Pydantic 约束输入输出，支持校验、重试、错误分类和审计日志。",
        ],
        "xiaohongshu": [
            "标题：Agent 调工具，最怕的不是不会调，而是乱调。",
            "解释 tool schema 就像表单字段：名字清楚、类型严格、少而准，系统才敢执行。",
            "用一个 create_task 示例展示自然语言如何变成结构化工具参数。",
        ],
        "validation_plan": [
            "准备 6 条输入，覆盖正确调用、缺参数、参数类型错、无权限、超时和工具异常。",
            "检查每条 tool_calls.jsonl 都有 run_id、tool_name、status、error_code。",
            "确认下游只消费结构化 JSON，不解析自然语言。",
        ],
    },
    {
        "priority": "Job-P0-03",
        "topic": "RAG Foundation / Enterprise Knowledge Base",
        "summary": "RAG 基础链路解决企业 Agent 如何可靠读取私有知识、给出引用并评估答案可信度。",
        "learn_focus": "文档解析、chunking、embedding、hybrid search、rerank、citation 和 RAG eval。",
        "interview_value": "RAG 仍是企业 Agent 最常见入口，面试会追问检索、重排、引用和评测，而不只是向量库。",
        "workbench_problem": "工作台需要从 Obsidian、项目文档和产物中检索上下文，否则 Agent 只能靠短上下文记忆。",
        "multi_agent_position": "位于 Knowledge Store 与 Agent Runtime 之间，为 Research/Writer/Reviewer 提供可溯源上下文。",
        "data_model": [
            "documents(id, path, title, source_type, updated_at)",
            "chunks(id, document_id, chunk_index, text, heading_path, token_count)",
            "retrieval_events(id, run_id, query, chunk_ids, scores, rerank_scores)",
        ],
        "api_design": [
            "POST /knowledge/ingest：解析并切分文档。",
            "POST /knowledge/search：执行 keyword/vector/hybrid 检索。",
            "POST /knowledge/rerank：对候选 chunk 重排。",
            "GET /knowledge/citations/{answer_id}：查看答案引用来源。",
        ],
        "core_architecture": [
            "Ingestion pipeline 负责解析、清洗、切分和元数据抽取。",
            "Retriever 先召回高 recall 候选。",
            "Reranker 提升 precision。",
            "Answer composer 强制带 citation。",
            "Eval harness 分别评估 retrieval 和 generation。",
        ],
        "key_modules": [
            "Chunker：按标题层级、长度和语义边界切分。",
            "Hybrid retriever：结合关键词和语义召回。",
            "Citation builder：把答案句子关联到 chunk_id。",
            "RAG evaluator：统计 recall@k、context precision、faithfulness。",
        ],
        "engineering_implementation": [
            "先用 5-10 篇 Markdown 做本地知识库，不急着接真实向量库。",
            "每个 chunk 保留 document path、heading_path 和 chunk_id，方便引用。",
            "把检索 trace 写入 retrieval_events，排查是检索错还是生成错。",
            "准备固定问题集，每次改 chunk/rerank/prompt 后跑回归。",
        ],
        "mini_demo": [
            "读取 5 篇 Markdown，按标题切成 chunks。",
            "用关键词或简单向量 mock 检索 top_k。",
            "输出 answer.md，要求每个结论带 chunk_id 引用。",
            "生成 rag_eval_report.md，记录命中和失败样例。",
        ],
        "interview_questions": [
            "RAG 完整链路是什么？",
            "chunk 太大或太小分别有什么问题？",
            "如何判断是检索错还是模型生成错？",
        ],
        "resume_project": [
            "写成：构建本地 RAG 知识库，支持文档切分、混合检索、引用溯源和回归评测，服务多 Agent 工作台上下文注入。",
        ],
        "xiaohongshu": [
            "标题：RAG 不是“接个向量库”这么简单。",
            "把企业知识库拆成切分、召回、重排、引用、评测五步。",
            "提醒：没有引用和评测的 RAG，很难说明答案可靠。",
        ],
        "validation_plan": [
            "准备 10 条问题，标注 expected_chunk_keyword。",
            "统计 top_3 是否命中相关 chunk。",
            "检查最终答案是否包含 citation，且 citation 文本支持答案。",
        ],
    },
    {
        "priority": "Job-P0-04",
        "topic": "LangGraph / Stateful Orchestration",
        "summary": "LangGraph/状态编排把 Agent 流程从不可控 while loop 变成可恢复、可中断、可审计的状态图。",
        "learn_focus": "StateGraph、node、edge、checkpoint、conditional edge、interrupt 和 human-in-the-loop。",
        "interview_value": "生产级 Agent 往往是 workflow + agent 混合，能讲状态图比只讲 ReAct 更工程化。",
        "workbench_problem": "工作台任务有检索、工具调用、审查、人工确认和产物写入，必须显式管理状态和恢复点。",
        "multi_agent_position": "位于 Orchestrator 核心，负责把多个 Agent/工具节点连接成可持久化 workflow。",
        "data_model": [
            "workflow_runs(id, graph_name, state_json, status, checkpoint_id)",
            "workflow_nodes(id, run_id, node_name, input_json, output_json, status)",
            "checkpoints(id, run_id, state_json, created_at)",
        ],
        "api_design": [
            "POST /workflows/start：启动状态图。",
            "POST /workflows/{id}/resume：从 checkpoint 恢复。",
            "POST /workflows/{id}/interrupt：暂停等待人工输入。",
            "GET /workflows/{id}/history：查看状态历史。",
        ],
        "core_architecture": [
            "Graph definition 定义节点和边。",
            "State object 保存共享上下文。",
            "Checkpoint store 保存每步后的可恢复状态。",
            "Human gate 在高风险节点暂停。",
            "Trace exporter 输出节点级运行日志。",
        ],
        "key_modules": [
            "Planner node：判断是否需要检索或工具。",
            "Retriever node：注入 RAG 上下文。",
            "Tool node：执行工具调用。",
            "Review node：校验输出并决定是否人工确认。",
        ],
        "engineering_implementation": [
            "先把一个 Agent while loop 拆成 4-6 个明确节点。",
            "每个节点只读写 state 的固定字段，避免随手塞字符串。",
            "在工具写入、发布、记忆固化前加 interrupt。",
            "把 checkpoint_id 写入 run trace，支持失败恢复和回放。",
        ],
        "mini_demo": [
            "实现 user_task → need_retrieval → retrieve → need_tool → call_tool → review → final 的状态图。",
            "中间保存 state_history.jsonl。",
            "在 publish 节点模拟人工 approve/reject。",
        ],
        "interview_questions": [
            "为什么生产级 Agent 需要状态机？",
            "LangGraph 的 node、edge、state 分别是什么？",
            "checkpoint 对失败恢复有什么价值？",
        ],
        "resume_project": [
            "写成：基于状态图编排多步骤 Agent 流程，支持 checkpoint、人工审批、状态历史和失败恢复。",
        ],
        "xiaohongshu": [
            "标题：Agent 为什么不能一直 while loop？",
            "用流程图解释：每一步有输入输出、有状态、有恢复点，系统才敢上线。",
            "把 checkpoint 类比游戏存档：失败后从关键节点继续，而不是重头来过。",
        ],
        "validation_plan": [
            "构造一次工具失败，确认 workflow 可以从上一个 checkpoint 恢复。",
            "构造一次人工拒绝，确认流程停止且记录 decision。",
            "检查 state_history 每步都有 node_name、status 和 state diff。",
        ],
    },
    {
        "priority": "Job-P0-05",
        "topic": "Evaluation / Eval Harness",
        "summary": "Eval Harness 用固定测试集和指标证明 Agent 变好了还是变差了，是区分玩具 demo 和工程系统的分水岭。",
        "learn_focus": "测试集、expected tool、expected fields、trajectory eval、LLM-as-judge、失败样例分析。",
        "interview_value": "面试非常容易用“你怎么证明有效”区分候选人，eval 是最强回答之一。",
        "workbench_problem": "工作台会持续改 prompt、工具、RAG 和路由；没有评测集就不知道哪次改动引入退化。",
        "multi_agent_position": "横切 Agent Runtime、RAG、Tool Gateway 和 Prompt Registry，用于回归与质量门禁。",
        "data_model": [
            "eval_cases(id, input, expected_tool, expected_fields_json, expected_keywords)",
            "eval_runs(id, suite_name, config_version, score, created_at)",
            "eval_results(id, eval_run_id, case_id, passed, failure_reason, latency_ms, cost)",
        ],
        "api_design": [
            "POST /eval/runs：触发一次评测。",
            "GET /eval/runs/{id}/report：查看结果和失败样例。",
            "POST /eval/cases：新增测试样例。",
            "GET /eval/regressions：比较两个配置版本。",
        ],
        "core_architecture": [
            "Dataset 管理固定输入和期望。",
            "Runner 批量执行 Agent。",
            "Scorer 分别检查工具选择、字段完整性、答案要点和安全。",
            "Report 汇总成功率、失败类型、latency 和 cost。",
        ],
        "key_modules": [
            "Case schema：统一 input、expected_tool、expected_output_fields。",
            "Trajectory checker：检查是否走了正确工具路径。",
            "Answer checker：规则或 judge 检查答案要点。",
            "Regression reporter：比较两次 eval 的退化样例。",
        ],
        "engineering_implementation": [
            "先写 10 条 JSONL 测试样例，不追求大而全。",
            "每次改 prompt/tool/retriever 后都跑同一套 cases。",
            "把失败原因分类为 retrieval_miss、wrong_tool、bad_args、bad_answer、unsafe_action。",
            "报告里同时输出 success_rate、p95 latency 和 token/cost。",
        ],
        "mini_demo": [
            "创建 eval_cases.jsonl，包含 input、expected_tool、expected_fields、expected_answer_key_points。",
            "跑一个 mock Agent，生成 eval_results.jsonl。",
            "输出 eval_report.md，列出通过率和失败样例。",
        ],
        "interview_questions": [
            "Agent 怎么评估，为什么不能只看最终回答？",
            "RAG eval 和 Agent eval 有什么区别？",
            "LLM-as-judge 靠谱吗，如何校准？",
        ],
        "resume_project": [
            "写成：构建 Agent Eval Harness，使用 JSONL 测试集评估工具选择、字段完整性、答案质量、延迟和成本，支持回归分析。",
        ],
        "xiaohongshu": [
            "标题：怎么证明你的 Agent 真的变好了？",
            "解释固定测试集就像考试卷，每次改 prompt 都要重考。",
            "强调失败样例比平均分更重要，因为它告诉你哪里坏了。",
        ],
        "validation_plan": [
            "准备 10 条 case，至少覆盖 RAG、tool、structured output 和拒答。",
            "人为改坏一个 tool schema，确认 eval 能发现 wrong_tool 或 bad_args。",
            "比较两次 eval_report，列出新增失败样例。",
        ],
    },
    {
        "priority": "Job-P1-01",
        "topic": "Observability / Trace",
        "summary": "Observability/Trace 让 Agent 失败时能定位是检索、模型、工具、状态还是权限出了问题。",
        "learn_focus": "run trace、step trace、tool trace、latency、cost、error type、prompt version。",
        "interview_value": "AgentOps/LLMOps 岗位会重点看你是否能调试和监控多步 Agent，而不是只看效果截图。",
        "workbench_problem": "多 Agent 工作台如果只保存最终回答，失败后无法复盘每个 Agent 做了什么、用了哪些上下文和工具。",
        "multi_agent_position": "横切 Orchestrator、Model Gateway、Tool Gateway、RAG 和 Artifact Store，是排障与评测的数据基础。",
        "data_model": [
            "traces(id, run_id, user_id, project_id, status, started_at, ended_at)",
            "trace_spans(id, trace_id, parent_span_id, span_type, name, latency_ms, status)",
            "trace_events(id, span_id, event_type, payload_json, created_at)",
        ],
        "api_design": [
            "POST /traces：创建 trace。",
            "POST /traces/{id}/spans：记录模型、工具、检索或状态节点 span。",
            "GET /traces/{id}：查看完整链路。",
            "GET /traces/{id}/errors：聚合失败原因。",
        ],
        "core_architecture": [
            "Trace context 在 API 入口生成并向下游传播。",
            "Span recorder 记录每个模型、工具、RAG、workflow 节点。",
            "Event store 保存输入摘要、输出摘要、错误和 artifact 引用。",
            "Debug UI 按 run_id 展示链路和耗时瀑布图。",
        ],
        "key_modules": [
            "Trace middleware：自动注入 trace_id。",
            "Model span：记录 model、tokens、cost、latency。",
            "Tool span：记录 tool_name、args_hash、status、error_code。",
            "Retrieval span：记录 query、chunk_ids、scores。",
        ],
        "engineering_implementation": [
            "先用 JSONL 写 trace，不急着接复杂平台。",
            "每个 span 保存摘要和引用，不直接塞完整敏感输入。",
            "按 error_type 做聚合：retrieval_miss、tool_error、model_format_error、policy_denied。",
            "把 prompt_version、model_version、config_version 一起写入 trace。",
        ],
        "mini_demo": [
            "模拟一次 Agent run：检索、工具调用、模型输出三步。",
            "生成 trace_events.jsonl。",
            "输出 trace_report.md，展示每步耗时、状态和失败原因。",
        ],
        "interview_questions": [
            "用户说 Agent 答错了，你怎么排查？",
            "trace 里必须记录哪些字段？",
            "如何区分 RAG 错、模型错和工具错？",
        ],
        "resume_project": [
            "写成：实现 Agent run trace，记录输入、检索片段、工具调用、模型输出、耗时与失败原因，支持按 run_id 回放和问题归因。",
        ],
        "xiaohongshu": [
            "标题：Agent 出错不可怕，可怕的是不知道错在哪。",
            "把 trace 类比快递物流：每一步都有时间、状态和异常原因。",
            "解释为什么最终回答截图不能证明系统可维护。",
        ],
        "validation_plan": [
            "构造一次 retrieval_miss、一次 tool_error、一次 model_format_error。",
            "确认 trace_report 能按 error_type 聚合。",
            "用 run_id 找到完整链路和对应 artifact。",
        ],
    },
    {
        "priority": "Job-P1-02",
        "topic": "MCP / Tool Protocol",
        "summary": "MCP 把工具、资源和提示模板标准化暴露给 AI 应用，减少每个工具都单独接入的重复工程。",
        "learn_focus": "MCP client/server、tools、resources、prompts、权限边界和 tool registry。",
        "interview_value": "MCP 是 Agent 工具接入的高频关键词，能讲清它和 function calling 的边界会很加分。",
        "workbench_problem": "工作台会接 Obsidian、搜索、文件、表格和外部系统；没有协议层就会变成一堆不可复用的私有工具。",
        "multi_agent_position": "位于 Tool Gateway 与外部工具生态之间，作为标准化工具和资源接入层。",
        "data_model": [
            "mcp_servers(id, name, endpoint, status, trust_level)",
            "mcp_capabilities(server_id, type, name, schema_json, description)",
            "mcp_invocations(id, run_id, server_id, capability_name, status, error_code)",
        ],
        "api_design": [
            "GET /mcp/servers：列出已接入 server。",
            "POST /mcp/servers/{id}/discover：发现 tools/resources/prompts。",
            "POST /mcp/tools/invoke：通过 Tool Gateway 调 MCP tool。",
            "GET /mcp/resources/search：检索 MCP resource。",
        ],
        "core_architecture": [
            "MCP Client 负责连接 server 和发现能力。",
            "Tool Gateway 负责权限、审计和调用包装。",
            "Capability Registry 保存 MCP 暴露的工具和资源。",
            "Policy Engine 判断 MCP 工具是否可用或需要审批。",
        ],
        "key_modules": [
            "Server discovery：同步 tools/resources/prompts。",
            "Schema mapper：把 MCP tool schema 映射到内部 capability。",
            "Invocation adapter：统一错误、超时和返回格式。",
            "Security wrapper：限制不可信 server 的权限和数据访问。",
        ],
        "engineering_implementation": [
            "先实现一个本地 mock MCP server，暴露 query_notes 和 write_mock_record。",
            "工作台启动时 discover server 能力，写入 Capability Registry。",
            "所有 MCP 调用仍走 Tool Gateway，不让 Agent 直接调用 server。",
            "给 server 配 trust_level，用 Policy Engine 控制可访问资源。",
        ],
        "mini_demo": [
            "写一个最小 MCP server 或 mock server。",
            "暴露 query_notes、write_json 两个工具。",
            "让 Agent 通过统一 gateway 调用并记录 mcp_invocations.jsonl。",
        ],
        "interview_questions": [
            "MCP 是什么，解决什么问题？",
            "MCP 和 function calling 有什么区别？",
            "MCP 工具有哪些安全风险？",
        ],
        "resume_project": [
            "写成：设计 MCP 接入层，将外部 tools/resources/prompts 注册为工作台 capability，并通过 Tool Gateway 做权限和审计。",
        ],
        "xiaohongshu": [
            "标题：MCP 为什么像 Agent 世界的 USB-C？",
            "解释它不是模型本身，而是让 AI 应用更标准地接工具和数据。",
            "提醒：标准接入不等于自动安全，权限和审计仍要做。",
        ],
        "validation_plan": [
            "discover 后检查 capability 数量和 schema。",
            "调用 query_notes 成功，调用高风险 write_json 触发审批或拒绝。",
            "确认 mcp_invocations 有 server_id、tool_name、status、error_code。",
        ],
    },
    {
        "priority": "Job-P1-03",
        "topic": "Guardrails / Agent Security Boundary",
        "summary": "Guardrails 和安全边界让 Agent 在能执行动作的同时保持权限可控、输入可信度可分级、风险可审计。",
        "learn_focus": "prompt injection、tool poisoning、权限分级、参数校验、敏感操作确认和审计。",
        "interview_value": "企业 Agent 比普通 RAG 风险更高，能讲安全边界会显得更像生产系统工程师。",
        "workbench_problem": "工作台 Agent 会读外部文档、写文件、调用工具和固化记忆；缺少 guardrails 会导致越权、污染和误操作。",
        "multi_agent_position": "横切 RAG、Tool Gateway、Memory、Artifact Store 和 Human Approval，是所有高风险动作前的控制层。",
        "data_model": [
            "security_policies(id, resource, action, condition, effect)",
            "risk_assessments(id, run_id, input_ref, risk_type, severity, decision)",
            "approval_required_actions(id, trace_id, action, payload_ref, status)",
        ],
        "api_design": [
            "POST /security/classify-input：识别 prompt injection 和敏感数据风险。",
            "POST /security/evaluate-action：判断工具/记忆/发布动作是否允许。",
            "POST /security/approval-required：创建人工确认任务。",
        ],
        "core_architecture": [
            "Input classifier 把外部文档内容视为 data 而非 instruction。",
            "Policy Engine 按资源、动作、主体和风险等级决策。",
            "Approval Center 接管高风险写入、发布、删除和记忆固化。",
            "Audit Log 保存所有 allow/deny/review 决策。",
        ],
        "key_modules": [
            "Prompt isolation：区分系统指令、用户指令和外部资料。",
            "Permission model：只读、安全写、高风险写分级。",
            "Schema validator：拦截非法参数和越权范围。",
            "Human approval：对不可自动判断动作暂停流程。",
        ],
        "engineering_implementation": [
            "给每个工具标注 read_only、safe_write、dangerous_write。",
            "外部文档检索内容只放 context，不允许覆盖系统规则。",
            "危险工具执行前必须生成 approval task。",
            "所有拒绝和审批都写入 risk_assessments 和 policy_decisions。",
        ],
        "mini_demo": [
            "准备一段带恶意指令的外部文档。",
            "让 Agent 检索它，但不能执行文档里的越权命令。",
            "调用 dangerous_write 时触发人工审批。",
        ],
        "interview_questions": [
            "Prompt injection 是什么？",
            "为什么 Agent 比普通 Chatbot 风险更高？",
            "怎么设计工具权限和人工确认？",
        ],
        "resume_project": [
            "写成：设计 Agent 安全边界，支持 prompt isolation、工具权限分级、敏感操作审批和全链路审计。",
        ],
        "xiaohongshu": [
            "标题：能执行动作的 Agent，必须先学会刹车。",
            "用“实习生拿到系统权限”类比：不是不让做事，而是高风险动作要审批、有记录。",
            "解释外部文档只能当资料，不能当新指令。",
        ],
        "validation_plan": [
            "构造 prompt injection 文档，确认系统只引用资料不执行指令。",
            "测试 read_only、safe_write、dangerous_write 三类工具权限。",
            "确认 dangerous_write 会进入 approval queue 且 workflow 暂停。",
        ],
    },
    {
        "priority": "Job-P1-04",
        "topic": "Backend Production Patterns for Agents",
        "summary": "后端生产化模式让 Agent 面对并发、长任务、重试、幂等、队列和成本时仍然稳定运行。",
        "learn_focus": "异步任务、队列、限流、重试、幂等、缓存、Docker/CI 和成本控制。",
        "interview_value": "不少 Agent 岗位本质是 AI + 后端工程，生产化关键词能直接抬高项目可信度。",
        "workbench_problem": "工作台多 Agent 并发运行、长任务和工具调用会遇到重复执行、队列堆积、超时和预算失控。",
        "multi_agent_position": "横切 API、Workflow Runtime、Model Gateway、Tool Gateway 和 Cost Metering，是生产运行底座。",
        "data_model": [
            "jobs(id, run_id, queue, status, attempts, idempotency_key, next_retry_at)",
            "rate_limit_buckets(scope, limit, used, reset_at)",
            "operation_locks(resource_id, holder_job_id, expires_at)",
        ],
        "api_design": [
            "POST /jobs/enqueue：提交异步 Agent task。",
            "GET /jobs/{id}：查询任务状态和重试次数。",
            "POST /idempotency/check：检查重复操作。",
            "POST /rate-limits/check：调用模型或工具前检查配额。",
        ],
        "core_architecture": [
            "API 接收任务后快速返回 job_id。",
            "Queue worker 执行长任务并保存状态。",
            "Retry scheduler 按错误类型做退避重试。",
            "Idempotency layer 防止重复写入和重复发布。",
            "Budget guard 在高成本任务前做检查或降级。",
        ],
        "key_modules": [
            "Task queue：隔离请求峰值和慢工具。",
            "Retry policy：区分可重试和不可重试错误。",
            "Idempotency key：保护写入类工具。",
            "Rate limiter：控制模型、工具和用户级配额。",
        ],
        "engineering_implementation": [
            "先用本地 JSONL 队列模拟异步任务，不急着引入 Redis。",
            "所有写入类工具必须带 idempotency_key。",
            "对 timeout/model_rate_limit 做指数退避，对 validation_error 不重试。",
            "为每个 run 记录 token 预算，超限时降级或进入人工确认。",
        ],
        "mini_demo": [
            "提交 12 个 mock Agent jobs 到本地队列。",
            "设置每分钟 5 次模型调用限制。",
            "模拟 2 个 timeout 自动重试，1 个重复写入被 idempotency 拦截。",
            "输出 queue_report.md。",
        ],
        "interview_questions": [
            "Agent 长任务怎么处理？",
            "工具重复调用怎么办？",
            "队列满了应该阻塞、拒绝还是降级？",
        ],
        "resume_project": [
            "写成：实现 Agent 后端生产化机制，支持异步队列、限流、退避重试、幂等去重和预算保护。",
        ],
        "xiaohongshu": [
            "标题：Agent 项目像不像生产系统，就看这些后端细节。",
            "列出队列、重试、幂等、限流、成本五个关键词。",
            "解释为什么 demo 能跑一次不等于系统能稳定服务很多用户。",
        ],
        "validation_plan": [
            "提交超过 rate limit 的任务，确认进入排队或降级。",
            "重复提交同一 idempotency_key，确认只写一次。",
            "模拟 timeout，确认只对可重试错误做退避重试。",
        ],
    },
]


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _section_list(items: list[str], fallback: str = "待补充。") -> str:
    values = [item.strip() for item in items if item.strip()]
    if not values:
        return f"- {fallback}"
    return "\n".join(f"- {item}" for item in values)


def _sources(value: Any) -> str:
    if not value:
        return "- 本条为 fallback/基础原理卡，未绑定当天新增来源。"
    rows = []
    for item in value if isinstance(value, list) else [value]:
        if isinstance(item, dict):
            title = str(item.get("title") or item.get("url") or "source")
            url = str(item.get("url") or "")
            note = str(item.get("note") or "")
            published = str(item.get("published") or item.get("date") or "")
            suffix_parts = [part for part in [published, note] if part]
            suffix = f"：{'；'.join(suffix_parts)}" if suffix_parts else ""
            if url:
                rows.append(f"- [{title}]({url}){suffix}")
            else:
                rows.append(f"- {title}{suffix}")
        else:
            rows.append(f"- {item}")
    return "\n".join(rows)


def _fallback_topic_by_index(index: int) -> dict[str, Any]:
    return dict(FALLBACK_TOPICS[index % len(FALLBACK_TOPICS)])


def _existing_research_texts(ctx: WorkstationContext) -> list[str]:
    research_dir = ctx.target_root / "06_Learning" / "Agent" / "前沿研究"
    if not research_dir.exists():
        return []
    texts: list[str] = []
    for path in research_dir.glob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        texts.append(text)
    return texts


def _existing_fallback_count(ctx: WorkstationContext) -> int:
    return sum(1 for text in _existing_research_texts(ctx) if "\nnovelty: fallback\n" in text)


def _topic_was_covered(ctx: WorkstationContext, topic: str) -> bool:
    frontmatter_topic = f"\ntopic: {topic}\n"
    heading = f"# {topic}\n"
    quoted_frontmatter_topic = f'\ntopic: "{topic}"\n'
    for text in _existing_research_texts(ctx):
        if frontmatter_topic in text or quoted_frontmatter_topic in text or heading in text:
            return True
    return False


def _fallback_topic(ctx: WorkstationContext) -> dict[str, Any]:
    current_mainline = str(ctx.config.get("current_mainline") or "").strip()
    for topic in JOB_MARKET_FALLBACK_TOPICS:
        if not _topic_was_covered(ctx, str(topic["topic"])):
            return dict(topic)
    if current_mainline == "多 Agent 协作工作台":
        for topic in MULTI_AGENT_WORKBENCH_FALLBACK_TOPICS:
            if not _topic_was_covered(ctx, str(topic["topic"])):
                return dict(topic)
    return _fallback_topic_by_index(_existing_fallback_count(ctx))


def fallback_payload(ctx: WorkstationContext, note_date: str) -> dict[str, Any]:
    base = _fallback_topic(ctx)
    current_mainline = str(ctx.config.get("current_mainline") or "").strip()
    priority = str(base.get("priority") or "")
    if priority.startswith("Job-"):
        source = "agent-job-market-fallback-queue"
        reason = "无论当天是否检索到合格新内容，都按 2026 年 6 月中旬 Agent 岗位要求 fallback 队列选择一个未讲过的高优先级工程主题。"
    elif current_mainline == "多 Agent 协作工作台":
        source = "multi-agent-workbench-fallback-queue"
        reason = "岗位 fallback 队列已覆盖后，当前主线是“多 Agent 协作工作台”，按工作台模块 fallback 队列选择一个未讲过主题。"
    else:
        source = "fallback-queue"
        reason = "岗位 fallback 队列已覆盖后，按 P0 fallback 队列继续学习。"
    base.update(
        {
            "novelty": "fallback",
            "engineering_value": "high",
            "selection_reason": reason,
            "project": "Personal AI Workstation",
            "sources": [],
            "research_source": source,
            "source_priority": SOURCE_PRIORITY,
            "risks": [
                "不要把 fallback 基础主题误写成当天新发布。",
                "落地前要用本地 mini demo 或项目任务集验证。",
            ],
            "next_actions": [
                "完成 30-60 分钟 mini demo。",
                "把 demo 结果沉淀到对应项目日志或工程能力笔记。",
            ],
        }
    )
    return base


def load_payload(ctx: WorkstationContext, path: str | None, note_date: str) -> dict[str, Any]:
    if not path:
        return fallback_payload(ctx, note_date)
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    base = fallback_payload(ctx, note_date) if str(data.get("novelty") or "").lower() == "fallback" else {}
    base.update({key: value for key, value in data.items() if value not in (None, "", [])})
    return base


def agent_research_content(ctx: WorkstationContext, note_date: str, payload: dict[str, Any]) -> str:
    topic = str(payload.get("topic") or "AI Infra / AgentOps / LLMOps 每日学习")
    novelty = str(payload.get("novelty") or "fallback")
    engineering_value = str(payload.get("engineering_value") or "medium")
    project = str(payload.get("project") or "Personal AI Workstation")
    priority = str(payload.get("priority") or "")
    summary = str(payload.get("summary") or "待补充。")
    selection_reason = str(payload.get("selection_reason") or "由每日 AI Infra / AgentOps / LLMOps 自动化选择。")
    learn_focus = str(payload.get("learn_focus") or payload.get("engineering_problem") or "待补充。")
    interview_value = str(payload.get("interview_value") or "待补充。")
    workbench_problem = str(payload.get("workbench_problem") or learn_focus)
    multi_agent_position = _list(payload.get("multi_agent_position"))
    if not multi_agent_position:
        multi_agent_position = _list(payload.get("core_architecture") or payload.get("core_mechanism"))

    return frontmatter(
        {
            "type": "agent-research-note",
            "id": stable_id("agent-research", f"{note_date}-{topic}"),
            "date": note_date,
            "area": "Agent",
            "topic": topic,
            "priority": priority,
            "project": project,
            "status": "captured",
            "novelty": novelty,
            "engineering_value": engineering_value,
            "source": "personal_workstation.write_agent_research_note",
            "research_source": str(payload.get("research_source") or "daily-agentops-research-automation"),
            "preview": bool(ctx.config.get("preview_mode", True)),
            "human_review_required": True,
            "human_reviewed": False,
            "created": note_date,
            "updated": note_date,
        },
        ["agent", "agentops", "llmops", "ai-infra", "learning", "workstation"],
    ) + f"""# {topic}

## 今日判断
- date: {note_date}
- novelty: {novelty}
- priority: {priority or "new"}
- engineering_value: {engineering_value}
- selection_reason: {selection_reason}

## 主题一句话结论
{summary}

## 来源与证据
{_sources(payload.get("sources"))}

## 为什么值得学
- 学习重点：{learn_focus}
- 面试/项目价值：{interview_value}

## 这个模块解决工作台里的什么问题
{workbench_problem}

## 它在多 Agent 架构中的位置
{_section_list(multi_agent_position)}

## 核心数据结构或表设计
{_section_list(_list(payload.get("data_model") or payload.get("core_data_structures")))}

## 核心 API 设计
{_section_list(_list(payload.get("api_design") or payload.get("core_api_design")))}

## 核心架构
{_section_list(_list(payload.get("core_architecture") or payload.get("core_mechanism")))}

## 关键模块
{_section_list(_list(payload.get("key_modules")))}

## 工程落地
{_section_list(_list(payload.get("engineering_implementation") or payload.get("implementation_steps")))}

## 面试追问
{_section_list(_list(payload.get("interview_questions")))}

## 最小 demo
{_section_list(_list(payload.get("mini_demo")))}

## 30-60 分钟 mini demo
{_section_list(_list(payload.get("mini_demo")))}

## 如何写进我的简历项目
{_section_list(_list(payload.get("resume_project")))}

## 如何写成小红书科普
{_section_list(_list(payload.get("xiaohongshu")))}

## 验证方法
{_section_list(_list(payload.get("validation_plan")))}

## 风险与适用边界
{_section_list(_list(payload.get("risks")))}

## 下一步实践
{_section_list(_list(payload.get("next_actions")))}

## 人工复核
- human_reviewed: false
- human_review_required: true
"""


def create_agent_research_note(
    ctx: WorkstationContext,
    note_date: str | None = None,
    input_json: str | None = None,
):
    note_date = note_date or today_string(ctx)
    payload = load_payload(ctx, input_json, note_date)
    topic = str(payload.get("topic") or "AI Infra AgentOps LLMOps 每日学习")
    path = ctx.target_root / "06_Learning" / "Agent" / "前沿研究" / f"{note_date}_{safe_slug(topic)}.md"
    results = [
        write_text_file(
        path,
        agent_research_content(ctx, note_date, payload),
        overwrite=bool(ctx.config.get("allow_overwrite", False)),
        unique_on_conflict=True,
        )
    ]
    if input_json and str(payload.get("novelty") or "").lower() != "fallback":
        fallback = fallback_payload(ctx, note_date)
        fallback_topic = str(fallback.get("topic") or "AI Infra AgentOps LLMOps fallback")
        fallback_path = ctx.target_root / "06_Learning" / "Agent" / "前沿研究" / f"{note_date}_{safe_slug(fallback_topic)}.md"
        results.append(
            write_text_file(
                fallback_path,
                agent_research_content(ctx, note_date, fallback),
                overwrite=bool(ctx.config.get("allow_overwrite", False)),
                unique_on_conflict=True,
            )
        )
    return results[0] if len(results) == 1 else results


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a daily AI Infra / AgentOps / LLMOps learning note.")
    parser.add_argument("--config", default=None)
    parser.add_argument("--date", default=None)
    parser.add_argument("--input-json", default=None)
    args = parser.parse_args()
    ctx = make_context(args.config)
    result = create_agent_research_note(ctx, args.date, args.input_json)
    print(f"{result.action}: {result.path}")


if __name__ == "__main__":
    main()
