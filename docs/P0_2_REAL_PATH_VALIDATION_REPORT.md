# P0.2 Real Path Validation Report

日期：2026-06-16

## 1. 结论

P0.2 已完成真实路径验收收口：

- 真实 LangGraph：可用，graph eval/demo 运行时记录为 `langgraph`
- 真实 BM25：可用，`rank_bm25.BM25Okapi` 可导入，检索结果 `retriever_type=bm25`
- 真实 LLM structured extraction：跳过，原因是 `.env` 缺少 `OPENAI_MODEL`
- fallback 路径：可用，无外部 API 时仍可完成风险规则、报告安全边界和 BM25 检索
- Artifact：已生成 `artifacts/p0_2_eval_comparison.json`

当前建议进入 P0.3，而不是直接进入 P1：先补齐 `OPENAI_MODEL` 并复测真实 LLM 抽取，再决定是否进入服务化和部署设计。

## 2. 环境检查

命令：

```powershell
python scripts\check_p0_env.py
```

结果：

- `langgraph`: present
- `langchain_openai`: present
- `rank_bm25`: present
- `pydantic`: present
- `python_dotenv`: present
- `.env`: present
- `OPENAI_API_KEY`: present
- `OPENAI_BASE_URL`: present
- `OPENAI_MODEL`: missing
- mode: `partial-real`

依赖安装命令 `python -m pip install -r requirements.txt` 已执行成功，核心依赖均已存在于当前 Python 环境。

## 3. 本次新增或改动

新增：

- `scripts/validate_real_extractor.py`
- `scripts/validate_real_bm25.py`
- `docs/P0_2_REAL_PATH_VALIDATION_REPORT.md`
- `artifacts/p0_2_eval_comparison.json`
- `artifacts/p0_2_sft_oracle_predictions.jsonl`

主要改动：

- `app/chains/turn_extractor.py`
  - 支持 `fake`、`fallback`、`real_llm` 抽取模式
  - 记录 `extractor_mode`、`model_name`、`error_type`
  - 缺少真实 LLM 配置时显式 fallback，不伪装为真实调用成功
- `app/chains/report_chain.py`
  - 旧 JSON prompt fallback 兼容 `OPENAI_MODEL` 和旧 `MODEL_NAME`
- `app/graphs/consultation_state.py`
- `app/graphs/consultation_nodes.py`
- `app/graphs/consultation_graph.py`
  - 记录真实 `graph_runtime`
  - 将抽取模式、fallback 状态、schema 指标写入 `RunState.metadata`
- `app/rag/hybrid_retriever.py`
  - `hybrid` 无 dense 时标记为 `hybrid_fallback`
  - `dense_only` 无 dense 时标记为 `dense_fallback`
- `app/safety/report_safety.py`
  - 修复安全后处理误伤标准免责声明中“不能替代医生判断”的问题
- `scripts/run_graph_demo.py`
  - 增加 `--extractor fake|fallback|real_llm`
  - 默认非交互 smoke，避免验收命令卡住
- `scripts/eval_report.py`
  - 增加 `--extractor fake|fallback|real_llm`
  - 输出 P0.2 指标并更新 `artifacts/p0_2_eval_comparison.json`
- `tests/test_p0_turn_extractor.py`
- `tests/test_p0_consultation_graph.py`
- `tests/test_p0_hybrid_rag.py`
- `tests/test_p0_report_safety.py`
  - 覆盖 missing API fallback、graph metadata、真实 BM25 类型、安全免责声明保护

## 4. LangGraph 真实路径验证

命令：

```powershell
python scripts\run_graph_demo.py --extractor fake
python scripts\run_graph_demo.py --extractor fallback
```

结果：

- 两个 demo 均成功运行
- `graph_runtime: langgraph`
- fake 模式：
  - `extractor_mode: fake`
  - `fallback_used: False`
  - `final_schema_pass: True`
  - 生成 `observe` 报告
- fallback 模式：
  - `extractor_mode: fallback`
  - `fallback_used: True`
  - `final_schema_pass: True`
  - 持续高烧触发 `P0_RISK_HIGH_FEVER`
  - 生成 `urgent_visit` 报告

## 5. 真实 LLM 抽取验证

命令：

```powershell
python scripts\validate_real_extractor.py --limit 5
python scripts\eval_report.py --mode graph --extractor real_llm --failed-only
```

结果：

```text
real_llm_validation_skipped: missing_api_config
missing_api_config: OPENAI_MODEL
```

说明：未伪造真实 LLM 结果。当前 `.env` 里存在 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`，但缺少 `OPENAI_MODEL`，因此真实 LLM structured output 路径按要求跳过。

## 6. BM25 真实路径验证

命令：

```powershell
python scripts\validate_real_bm25.py --query "主诉：腹泻；观察建议" --top-k 3
python scripts\validate_real_bm25.py --query "持续高热 三天 风险提示" --top-k 3
python scripts\validate_real_bm25.py --query "胸痛 呼吸困难 线下就医" --top-k 3
```

结果：

- `real_bm25_available: true`
- 三个查询均返回 evidence
- 返回 chunk 的 `retriever_type` 均为 `bm25`
- 查询“持续高热 三天 风险提示”命中持续高热相关知识片段
- 查询“胸痛 呼吸困难 线下就医”命中胸痛/呼吸困难/线下就医相关知识片段

## 7. Eval 指标

命令：

```powershell
python scripts\eval_report.py --mode graph --extractor fake --failed-only
python scripts\eval_report.py --mode graph --extractor fallback --failed-only
python scripts\eval_report.py --mode graph --extractor real_llm --failed-only
```

fake 结果：

- passed: 17/20
- business_assertion_pass_rate: 85.0%
- raw_llm_json_valid_rate: 100.0%
- final_schema_pass_rate: 100.0%
- fallback_used_rate: 0.0%
- risk_recall_on_redflag_cases: 100.0%
- negation_accuracy: 100.0%
- rag_recall_at_3: 88.2%
- graph_runtime: `langgraph`
- real_bm25_available: true

fallback 结果：

- passed: 6/20
- business_assertion_pass_rate: 30.0%
- raw_llm_json_valid_rate: 0.0%
- final_schema_pass_rate: 100.0%
- fallback_used_rate: 100.0%
- risk_recall_on_redflag_cases: 100.0%
- negation_accuracy: 100.0%
- rag_recall_at_3: 50.0%
- graph_runtime: `langgraph`
- real_bm25_available: true

real_llm 结果：

- skipped: true
- skip_reason: `missing_api_config`
- missing: `OPENAI_MODEL`

对比结果已落盘：

```text
artifacts/p0_2_eval_comparison.json
```

## 8. 测试命令

通过：

```powershell
python -m py_compile app\chains\turn_extractor.py app\graphs\consultation_state.py app\graphs\consultation_nodes.py app\graphs\consultation_graph.py app\rag\bm25_retriever.py app\rag\hybrid_retriever.py app\safety\report_safety.py scripts\run_graph_demo.py scripts\validate_real_extractor.py scripts\validate_real_bm25.py scripts\eval_report.py scripts\eval_sft_extract.py
python -m unittest tests.test_p0_turn_extractor
python -m unittest tests.test_p0_consultation_graph
python -m unittest tests.test_p0_hybrid_rag
python -m unittest tests.test_p0_risk_rules
python -m unittest tests.test_p0_report_safety
python scripts\eval_sft_extract.py --pred-file artifacts\p0_2_sft_oracle_predictions.jsonl
git diff --check
```

说明：

- `git diff --check` 仅输出 CRLF 提示，无 whitespace error
- SFT eval 使用 `artifacts/p0_2_sft_oracle_predictions.jsonl`，这是 oracle 预测文件，用于验证评估脚本链路，不代表模型效果
- 测试中出现的 transformers/PyTorch 版本提示不影响 P0.2 主路径

## 9. 遗留问题

1. 真实 LLM structured output 尚未验证，阻塞项是 `OPENAI_MODEL` 缺失。
2. fallback 模式仅做安全兜底和风险规则，不做完整语义抽取，因此业务断言仍只有 30.0%。
3. fake 模式仍有 3 个失败 case，集中在弱主诉、无伴随症状短语和症状 none -> present 的轻量规则覆盖。
4. dense/vector/reranker 仍是 P0 架构占位，本次未进入 P1 实现。

## 10. 建议

建议进入 P0.3：

1. 在 `.env` 中补齐 `OPENAI_MODEL`。
2. 复跑 `validate_real_extractor.py` 和 `eval_report.py --mode graph --extractor real_llm`。
3. 对 fake/fallback 暴露的 3 个轻量抽取规则缺口做小修。
4. 真实 LLM 指标稳定后，再进入 P1 的 FastAPI、vLLM/LiteLLM、向量检索和观测链路设计。

## P0.3 Real LLM Structured Extraction Validation

P0.3 报告见 `docs/P0_3_REAL_LLM_VALIDATION_REPORT.md`。
