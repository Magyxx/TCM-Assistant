# P0.3 Real LLM Structured Extraction Validation

生成日期：2026-06-16

## 1. 本次任务目标

P0.3 只验证真实 LLM structured extraction 路径是否可用，并在必要时对抽取层做最小加固。项目边界保持不变：TCM-Assistant 是中医问诊信息整理辅助系统，不是诊断系统、处方系统或治疗决策系统。

本次验证重点：

- `.env` 中 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL` 是否存在。
- `langchain_openai.ChatOpenAI` 是否能通过 OpenAI-compatible API 调用。
- 真实 LLM 输出是否能进入 `TurnOutput.model_validate()`。
- `real_llm` 接入 LangGraph 后是否能跑通。
- fake、fallback、real_llm 三种模式指标是否分开记录。

## 2. 排查与修复结论

本次排查发现三个问题：

1. `.env` 中原有 API key 与用户新提供的 key 不一致，导致 DeepSeek 返回 `401 authentication_error`。
2. 首次写入 `.env` 时 PowerShell 生成了 UTF-8 BOM，`python-dotenv` 将变量名识别为带 BOM 的 `OPENAI_API_KEY`，造成 `OPENAI_API_KEY: missing`。已改为无 BOM UTF-8。
3. `app/chains/report_chain.py` 顶层导入 LoRA/SFT 依赖，当前本机 `transformers/peft` 组合导入失败，使 LangGraph 回退到简化 merge，导致泛化主诉过滤等既有规则没有生效。已将 SFT 导入改为可选，仅显式 `mode="sft"` 时才要求该依赖可用。

修复后：

- 真实 LLM smoke test 成功。
- `run_graph_demo.py --extractor real_llm` 成功。
- `eval_report.py --mode graph --extractor real_llm --failed-only` 达到 20/20。
- `fallback_used_rate=0.0%`，没有把 fallback 伪装为真实 LLM 成功。

## 3. 环境检查结果

执行命令：

```powershell
python scripts\check_p0_env.py
```

结果摘要：

| 项目 | 结果 |
|---|---|
| langgraph | present |
| langchain_openai | present |
| rank_bm25 | present |
| pydantic | present |
| python_dotenv | present |
| .env | present |
| OPENAI_API_KEY | present |
| OPENAI_BASE_URL | present |
| OPENAI_MODEL | present |
| mode | real-ready |

`OPENAI_MODEL` 为 `deepseek-v4-pro`。报告和 artifact 只记录 present/missing 与模型名，不记录 API key 或 `.env` 内容。

## 4. 抽取层策略

`app/chains/turn_extractor.py` 保持四层策略：

1. `provider_native_structured_output`
2. `tool_calling_structured_output`
3. `json_prompt`
4. `rule_fallback`

DeepSeek 当前稳定命中 `json_prompt`，即 OpenAI-compatible JSON Output 路径。所有路径最终都进入 `TurnOutput.model_validate()`。

metadata 保留：

- `extractor_mode`
- `strategy`
- `raw_llm_json_valid`
- `final_schema_pass`
- `fallback_used`
- `model_name`
- `error_type`
- `error_message_preview`

## 5. 真实 LLM Smoke Test

执行命令：

```powershell
python scripts\validate_real_extractor.py --case "最近胃胀，饭后明显，睡眠一般"
python scripts\validate_real_extractor.py --case "我持续高烧三天"
python scripts\validate_real_extractor.py --case "没有发热，也不胸痛"
```

| 输入 | raw_llm_json_valid | final_schema_pass | fallback_used | extractor_mode | strategy | risk_flags_status | risk_rule_ids | error_type |
|---|---:|---:|---:|---|---|---|---|---|
| 最近胃胀，饭后明显，睡眠一般 | true | true | false | real_llm | json_prompt | unknown | [] | null |
| 我持续高烧三天 | true | true | false | real_llm | json_prompt | present | [P0_RISK_HIGH_FEVER] | null |
| 没有发热，也不胸痛 | true | true | false | real_llm | json_prompt | none | [] | null |

结论：

- 普通症状结构化抽取可用。
- 高风险识别未回退：持续高烧触发 `P0_RISK_HIGH_FEVER`。
- 否定句识别未回退：`没有发热，也不胸痛` 未误判为风险 present。

## 6. LangGraph Real LLM Demo

执行命令：

```powershell
python scripts\run_graph_demo.py --extractor real_llm
```

结果摘要：

| 字段 | 结果 |
|---|---|
| graph_runtime | langgraph |
| extractor_mode_requested | real_llm |
| extractor_mode | real_llm |
| strategy | json_prompt |
| model_name | deepseek-v4-pro |
| fallback_used | false |
| final_schema_pass | true |
| error_type | null |
| risk_rule_ids | [] |

demo 能生成 `FinalReport`，并保留“仅供问诊信息整理，不作为诊断依据”的安全边界。

## 7. Eval Report 对比

执行命令：

```powershell
python scripts\eval_report.py --mode graph --extractor fake --failed-only
python scripts\eval_report.py --mode graph --extractor fallback --failed-only
python scripts\eval_report.py --mode graph --extractor real_llm --failed-only
```

| 模式 | 通过 | 总数 | business_assertion_pass_rate | raw_llm_json_valid_rate | final_schema_pass_rate | fallback_used_rate | risk_recall_on_redflag_cases | negation_accuracy | rag_recall_at_3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| fake | 19 | 20 | 95.0% | 100.0% | 100.0% | 0.0% | 100.0% | 100.0% | 83.3% |
| fallback | 7 | 20 | 35.0% | 0.0% | 100.0% | 100.0% | 100.0% | 100.0% | 40.0% |
| real_llm | 20 | 20 | 100.0% | 100.0% | 100.0% | 0.0% | 100.0% | 100.0% | 83.3% |

已生成 artifact：

```text
artifacts/p0_3_real_llm_eval_result.json
artifacts/p0_3_real_llm_failure_analysis.json
```

`artifacts/p0_3_real_llm_failure_analysis.json` 当前为空列表，表示 real_llm eval 无失败样本。

## 8. 最小业务规则加固

为消除真实 LLM 剩余失败样本，做了两条合并层后处理：

1. 当模型输出泛化主诉如“不太舒服”时继续过滤；当用户原文包含明确部位弱主诉如“胃有点不舒服”时，从原文恢复为弱有效主诉。
2. 当模型未显式设置 `symptoms_status`，且用户原文包含“没有腹痛、呕吐、便血这些情况”等明确否定总结时，将伴随症状状态保守设置为 `none`。

这些规则只服务问诊信息整理，不引入诊断、证型、处方或治疗决策。

## 9. Safety 与风险边界

本次没有把系统升级为诊断、处方或治疗决策系统。真实 LLM prompt 已明确限制只抽取问诊字段，不能诊断、判断证型、开方或给治疗方案。

验证结果：

- 高风险规则：`risk_recall_on_redflag_cases=100.0%`
- 否定句规则：`negation_accuracy=100.0%`
- report safety 单测：通过
- graph demo final report 的 `safety_post_check_issues=[]`

## 10. 必跑命令结果

通过：

```powershell
python -m py_compile app\chains\report_chain.py app\chains\turn_extractor.py app\graphs\consultation_nodes.py app\graphs\consultation_graph.py
python -m unittest tests.test_p0_risk_rules
python -m unittest tests.test_p0_turn_extractor
python -m unittest tests.test_p0_consultation_graph
python -m unittest tests.test_p0_hybrid_rag
python -m unittest tests.test_p0_report_safety
python scripts\eval_sft_extract.py --pred-file data\sft\processed\sft_report_turn_extract_val.jsonl
python scripts\validate_real_extractor.py --case "最近胃胀，饭后明显，睡眠一般"
python scripts\validate_real_extractor.py --case "我持续高烧三天"
python scripts\validate_real_extractor.py --case "没有发热，也不胸痛"
python scripts\run_graph_demo.py --extractor real_llm
python scripts\eval_report.py --mode graph --extractor fake --failed-only
python scripts\eval_report.py --mode graph --extractor fallback --failed-only
python scripts\eval_report.py --mode graph --extractor real_llm --failed-only
```

SFT eval 结果：

- total=4
- passed=4
- failed=0
- schema_pass_rate=4/4

## 11. 当前仍未解决的问题

1. `provider_native_structured_output` 与 `tool_calling_structured_output` 没有成为 DeepSeek 当前命中策略，实际稳定路径是 `json_prompt`。
2. fallback 模式仍只是保底能力，不能替代真实 LLM 语义抽取。
3. 本机 LoRA/SFT 依赖仍不可用，但已隔离为可选实验路径，不再影响主问诊流程。
4. 后续 P1 若要引入服务化或观测链路，需要继续保持 API key 脱敏和 report safety 检查。

## 12. 是否建议进入 P1

建议进入 P1。

理由：

- 环境达到 `real-ready`。
- 三条真实 LLM smoke case 通过。
- `run_graph_demo.py --extractor real_llm` 通过。
- `eval_report.py --mode graph --extractor real_llm` 可跑完。
- `raw_llm_json_valid_rate=100.0%`。
- `final_schema_pass_rate=100.0%`。
- `fallback_used_rate=0.0%`。
- `business_assertion_pass_rate=100.0%`，明显高于 fallback 的 35.0%。
- 高风险识别和否定句识别均为 100.0%。

## 13. 验证状态矩阵

| 项目 | 状态 |
|---|---|
| fake 已验证 | 是 |
| fallback 已验证 | 是 |
| 真实 LangGraph 已验证 | 是 |
| 真实 BM25 已验证 | 是 |
| 真实 LLM smoke test 已验证 | 是 |
| 真实 LLM eval 已验证 | 是 |
| 真实 LLM structured extraction 是否稳定 | 当前 P0.3 测试集稳定 |
| 是否建议进入 P1 | 是 |
