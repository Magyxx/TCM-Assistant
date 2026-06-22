# Phase 7 Validation

## Gate 指标
P7 gate 写入 `artifacts/p7_gate_report.json`，汇总 API、Storage、Memory、Tool Registry、RAG evidence persistence、Observability、Safety、Docker smoke、P5/P6 回归、unittest、compileall 和 JSON artifact validation。

## 验证脚本
- `python scripts/run_p7_api_validation.py`
- `python scripts/run_p7_storage_validation.py`
- `python scripts/run_p7_memory_validation.py`
- `python scripts/run_p7_tool_registry_validation.py`
- `python scripts/run_p7_observability_validation.py`
- `python scripts/run_p7_safety_validation.py`
- `python scripts/run_p7_docker_smoke.py`
- `python scripts/run_p7_failure_analysis.py`
- `python scripts/run_p7_gate.py`

## 主要验收项
- API health/session/turn/report/state restore 均通过。
- SQLite roundtrip、trace、memory snapshot、RAG evidence persisted。
- L4 不保存 PII 或真实患者原始对话。
- RAG evidence 不修改 `chief_complaint`、`duration`、`risk_status`、`risk_rule_ids`。
- 工具越权被拒绝，tool audit log 可保存。
- 报告无诊断/处方/治疗方案输出，高风险 false negative 为 0。
- fallback、real_llm、storage、docker 状态必须真实记录。

## Failure Modes
Docker CLI 不可用会记录为 docker runtime caution/failure，不伪造 `docker_smoke_pass=true`。real LLM 不可用继承 P5 的 caution 语义。PostgreSQL 未配置时只报告 schema-ready。
