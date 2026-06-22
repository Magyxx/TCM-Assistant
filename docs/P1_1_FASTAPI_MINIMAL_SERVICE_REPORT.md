# P1.1 FastAPI Minimal Service Report

生成日期：2026-06-16

## 1. P1.1 目标

P1.1 只做 FastAPI 最小服务化：在不改变现有 CLI、LangGraph、RAG、风险规则、安全后检查和评估闭环的前提下，新增 API 壳，让调用方可以创建问诊 session、提交一轮自然语言症状、查看当前状态和报告。

项目定位保持不变：TCM-Assistant 是中医问诊辅助系统，不是诊断系统、处方系统、治疗决策系统，也不是多 Agent 医生工作站。

## 2. P1.1 边界

本阶段没有引入：

- SQLite / PostgreSQL / ORM
- Storage 层
- MemoryManager
- Tool Registry
- Embedding / vector store
- MCP Server
- Web UI
- vLLM / LiteLLM
- Redis / Celery / Kafka
- GraphRAG
- 多 Agent 工作站
- 自动诊断、自动开方或治疗方案生成

session 仅保存在进程内 in-memory store，持久化留给 P1.2。

## 3. 新增 API 文件

新增：

```text
app/api/__init__.py
app/api/main.py
app/api/models.py
app/api/session_runtime.py
scripts/run_api_demo.py
tests/test_p1_1_api_minimal.py
docs/P1_1_FASTAPI_MINIMAL_SERVICE_REPORT.md
```

修改：

```text
requirements.txt
README.md
docs/P1_GATE_REPORT.md
app/graphs/consultation_state.py
app/graphs/consultation_nodes.py
app/graphs/consultation_graph.py
app/chains/turn_extractor.py
app/chains/report_chain.py
```

说明：

- `app/graphs/*` 仅增加向后兼容的 `rag_enabled` 参数，默认 `true`，不改变 CLI 原行为。
- `turn_extractor.py` 将 DeepSeek/OpenAI-compatible real LLM 稳定路径优先设置为 `json_prompt`。
- `report_chain.py` 收紧 tri-state 语义：空伴随症状列表不能把 `symptoms_status` 升为 `present`；同时过滤掉与主诉完全重复的伴随症状。

## 4. API Endpoint

### `GET /health`

返回服务健康状态，不依赖 API key，不调用 LLM，不调用 graph。

### `POST /sessions`

创建 in-memory session。

请求字段：

- `extractor_mode`: `real_llm` / `fake` / `fallback`，默认 `real_llm`
- `rag_enabled`: 默认 `true`

### `POST /sessions/{session_id}/turn`

提交一轮用户输入，调用现有 LangGraph 主流程 `run_consultation_graph()`。

返回：

- `session_id`
- `turn_id`
- `turn_count`
- `next_question`
- `state`
- `risk_flags_status`
- `risk_rule_ids`
- `risk_reasons`
- `final_report`
- `metadata`
- `safety_disclaimer`

### `GET /sessions/{session_id}/state`

返回当前 in-memory state。session 不存在时返回 404。

### `GET /sessions/{session_id}/report`

若已有 `FinalReport`，返回 `ready=true` 与报告；否则返回 `ready=false`、缺失字段和下一问。

## 5. 是否调用真实 LangGraph

是。API 层不重写问诊流程，`POST /sessions/{session_id}/turn` 直接调用：

```python
run_consultation_graph(
    session.run_state,
    user_input,
    extractor_mode=session.extractor_mode,
    rag_enabled=session.rag_enabled,
)
```

## 6. Session 是否 in-memory

是。`app/api/session_runtime.py` 使用模块级字典和 `RLock` 保存 session，不写数据库，不写 `.env`，不保存 API key。

## 7. 为什么不做 Storage / Memory / Embedding

P1.1 是 API 壳，不是产品化服务。Storage、Memory、Embedding、权限、观测链路和部署属于后续阶段。当前优先保证 P0 的 LangGraph 工作流可通过 HTTP 调用，同时不扩大医疗风险边界。

## 8. 测试结果

通过：

```powershell
python scripts\check_p0_env.py
python -m py_compile app\api\main.py app\api\models.py app\api\session_runtime.py scripts\run_api_demo.py
python -m unittest tests.test_p0_risk_rules
python -m unittest tests.test_p0_turn_extractor
python -m unittest tests.test_p0_consultation_graph
python -m unittest tests.test_p0_hybrid_rag
python -m unittest tests.test_p0_report_safety
python -m unittest tests.test_p1_1_api_minimal
python scripts\run_api_demo.py
python scripts\validate_real_extractor.py --case "最近胃胀，饭后明显，睡眠一般"
python scripts\run_graph_demo.py --extractor real_llm
python scripts\eval_report.py --mode graph --extractor real_llm --failed-only
python scripts\eval_sft_extract.py --pred-file data\sft\processed\sft_report_turn_extract_val.jsonl
git diff --check
```

## 9. P0 回归结果

- P0 risk rules: 13 tests OK
- P0 turn extractor: 9 tests OK
- P0 consultation graph: 7 tests OK
- P0 hybrid RAG: 6 tests OK
- P0 report safety: 6 tests OK
- real LLM eval: 20/20
- raw LLM JSON valid: 100.0%
- final schema pass: 100.0%
- fallback used: 0.0%
- risk recall: 100.0%
- negation accuracy: 100.0%
- business assertion pass rate: 100.0%
- SFT eval: 4/4
- `git diff --check`: 无 whitespace error，仅 Windows LF/CRLF warning

## 10. API Demo 结果

执行：

```powershell
python scripts\run_api_demo.py
```

结果摘要：

- session 创建成功
- 默认 demo 使用 `extractor_mode=fake`，不依赖真实 API
- 提交两轮输入成功
- `metadata.graph_runtime=langgraph`
- `metadata.extractor_mode=fake`
- `metadata.fallback_used=false`
- `GET /state` 成功
- `GET /report` 返回 `ready=false`，符合两轮 fake demo 尚未补齐所有核心字段的状态

本地 uvicorn 服务验证：

- URL: `http://127.0.0.1:8011`
- `GET /health` 返回 `{"status":"ok","service":"TCM-Assistant","stage":"P1.1","mode":"agentic_workflow","diagnosis_system":false}`

## 11. Secret 与安全边界

- API 不返回 `OPENAI_API_KEY`
- API 不返回 `sk-`
- API 不返回 `.env` 内容
- response 统一包含 `safety_disclaimer`
- FinalReport 仍经过既有 `report_safety.py` 后检查
- API 层没有输出诊断、证型、方剂、处方、药物建议或治疗方案

## 12. 是否建议进入 P1.2

建议进入 P1.2 SQLite 状态持久化，但仅在 P1.1 当前边界继续保持的前提下：

- 仍然只保存问诊 session 状态与回合记录
- 不保存 API key
- 不新增 MemoryManager
- 不新增 Embedding / vector store
- 不引入诊断、处方或治疗决策能力

P1.2 的建议目标：为当前 in-memory session store 增加最小 SQLite 持久化适配层，并保持 API schema 不破坏。
