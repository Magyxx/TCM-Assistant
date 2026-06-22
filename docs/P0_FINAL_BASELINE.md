# P0 Final Baseline

生成日期：2026-06-16

## 项目状态

TCM-Assistant 当前完成 P0 baseline freeze。项目定位保持为“中医问诊辅助系统”，用于把自然语言症状输入转化为结构化问诊状态，补齐核心信息，识别高风险信号，并生成结构化问诊摘要。

系统不是诊断系统、不是处方系统、不是治疗决策系统，也不是多 Agent 医生工作站。

## P0.1 状态

P0.1 完成 fallback-only 验收收口：

- deterministic fake extractor 已可用于本地测试。
- graph、risk rules、RAG、安全后检查单测已建立。
- 指标拆分为 `raw_llm_json_valid`、`final_schema_pass`、`fallback_used`。
- 已生成 `docs/P0_1_ACCEPTANCE_REPORT.md` 与相关 artifact。

## P0.2 状态

P0.2 完成真实路径验证：

- `graph_runtime=langgraph` 已在 demo/eval 中记录。
- 真实 LangGraph runtime 可用。
- 真实 BM25 可用。
- `rank_bm25` present。
- BM25 查询返回 `retriever_type=bm25`。
- real LLM 因缺少模型配置在 P0.2 时跳过，后续由 P0.3 完成。

## P0.3 状态

P0.3 已完成真实 LLM structured extraction 验证：

- `check_p0_env.py`: `real-ready`
- 三条 smoke case: `real_llm + json_prompt`，`fallback_used=false`
- `run_graph_demo.py --extractor real_llm`: 通过
- `eval_report.py --mode graph --extractor real_llm`: 20/20
- `raw_llm_json_valid_rate`: 100.0%
- `final_schema_pass_rate`: 100.0%
- `fallback_used_rate`: 0.0%
- `risk_recall_on_redflag_cases`: 100.0%
- `negation_accuracy`: 100.0%
- `business_assertion_pass_rate`: 100.0%
- fake: 19/20
- fallback: 7/20
- real_llm: 20/20
- P0 单测全部通过
- `eval_sft_extract.py`: 4/4

## 三模式最终指标

| 模式 | 通过 | 总数 | 业务通过率 | raw JSON | schema | fallback | 风险召回 | 否定准确率 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fake | 19 | 20 | 95.0% | 100.0% | 100.0% | 0.0% | 100.0% | 100.0% |
| fallback | 7 | 20 | 35.0% | 0.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| real_llm | 20 | 20 | 100.0% | 100.0% | 100.0% | 0.0% | 100.0% | 100.0% |

## 脱敏检查

结果：

- `.env` 已加入 `.gitignore`。
- `.env` 已从 Git 索引移除，保留本地文件。
- 可提交文件集合中 `sk-` secret 模式命中文件数：0。
- 可提交文件集合中 `OPENAI_API_KEY=` 赋值文件数：1，仅 `.env.example` 占位示例。
- 可提交文件集合中存在 `OPENAI_API_KEY` 环境变量名引用，属于代码读取环境变量，不包含 secret。
- P0.3 报告与 artifact 中 `sk-` 计数：0。

## 必跑命令结果

通过：

```powershell
python scripts\check_p0_env.py
python -m unittest tests.test_p0_risk_rules
python -m unittest tests.test_p0_turn_extractor
python -m unittest tests.test_p0_consultation_graph
python -m unittest tests.test_p0_hybrid_rag
python -m unittest tests.test_p0_report_safety
python scripts\validate_real_extractor.py --case "最近胃胀，饭后明显，睡眠一般"
python scripts\run_graph_demo.py --extractor real_llm
python scripts\eval_report.py --mode graph --extractor real_llm --failed-only
python scripts\eval_sft_extract.py --pred-file data\sft\processed\sft_report_turn_extract_val.jsonl
git diff --check
```

说明：

- `git diff --check` 无 whitespace error，仅 Windows LF/CRLF warning。
- 单元测试中的 transformers/PyTorch 版本提示不影响 P0 baseline。

## 冻结结论

P0 completed, P1 ready。

P0 baseline 可作为后续 P1 最小服务化、观测链路和部署前的稳定参考点。后续 P1 不应改变 P0 的安全边界：系统只做问诊信息整理，不做诊断、开方或治疗决策。
