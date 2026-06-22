# P1 Gate Report

生成日期：2026-06-16

## Gate 结论

P1 gate passed。

TCM-Assistant 可以进入 P1，但 P1 仍必须保持项目定位：中医问诊辅助系统，不是诊断系统、处方系统、治疗决策系统或多 Agent 医生工作站。

## 允许进入 P1 的原因

P0.3 已满足进入 P1 的核心条件：

- 环境检查达到 `real-ready`。
- 真实 LLM smoke case 三条均通过。
- 真实 LLM 抽取策略稳定命中 `json_prompt`。
- `TurnOutput.model_validate()` 通过率为 100.0%。
- `run_graph_demo.py --extractor real_llm` 通过。
- `eval_report.py --mode graph --extractor real_llm` 达到 20/20。
- `fallback_used_rate=0.0%`，真实 LLM 结果没有被 fallback 伪装。
- 高风险识别和否定句识别均为 100.0%。
- report safety 单测通过，demo final report 保留安全边界。
- `.env` 已加入 `.gitignore` 并从 Git 索引移除。
- 可提交文件集合脱敏扫描未发现 `sk-` secret 模式。

## P1 入口建议

建议进入 P1.1 FastAPI 最小服务化，但范围应保持克制：

- 只封装现有 LangGraph 主流程。
- 不新增诊断、处方、治疗决策能力。
- 不引入 MemoryManager、多 Agent、Tool Registry、Embedding、向量库或生产级存储。
- API 输出必须继续保留 `FinalReport` 安全边界。
- 服务层必须复用 P0 的 `RunState`、`TurnOutput`、风险规则、安全后检查与 eval 闭环。

## P1 Gate 风险提醒

- `.env` 仍存在于本地用于验证，但已被忽略，不应提交。
- P1 如果引入服务化，需要补充请求级脱敏日志策略。
- P1 如果引入多用户会话，需要先定义最小状态生命周期，避免过早进入复杂存储或权限系统。
- P1 不应把 RAG 内容扩展为诊断知识库或处方建议库。

## 最终判断

P1 gate passed。建议下一步进入 P1.1 FastAPI 最小服务化。

## P1.1 FastAPI Minimal Service

P1.1 报告见 `docs/P1_1_FASTAPI_MINIMAL_SERVICE_REPORT.md`。

## P1.2 SQLite Persistence

P1.2 adds minimal local SQLite persistence for the existing FastAPI runtime
session layer. It persists session metadata, current `RunState` JSON, and turn
history while keeping the P1.1 API endpoint contract unchanged.

P1.2 remains inside the P1 safety boundary:

- no MemoryManager
- no Embedding or vector store
- no RAG expansion
- no Tool Registry
- no multi-agent workflow
- no Web UI
- no user or permission system
- no diagnosis, prescription, or treatment-plan output

Report: `docs/P1_2_SQLITE_PERSISTENCE_REPORT.md`.

## P1.3 SQLite Persistence Hardening

P1.3 hardens the P1.2 SQLite store without changing the P1.1 API contract or
the P1.2 session/state/turn recovery behavior.

P1.3 adds:

- `schema_meta` version metadata
- idempotent SQLite initialization for empty and legacy P1.2 databases
- shared redaction utilities
- SQLite inspect script
- exception-path tests for schema and transaction behavior

P1.3 remains inside the P1 safety boundary:

- no ORM
- no MemoryManager
- no Embedding or vector store
- no Tool Registry
- no multi-agent workflow
- no Web UI
- no user or permission system
- no diagnosis, prescription, or treatment-plan output

Report: `docs/P1_3_SQLITE_HARDENING_REPORT.md`.

## P1.4 API Stability, Error Contract, Replay

P1.4 stabilizes the existing P1 API surface under invalid input, missing or
corrupted state, and replay conditions. It adds a uniform error response shape,
input-boundary tests, a local replay harness, and an API contract snapshot while
preserving all P1.1 success response contracts.

P1.4 remains inside the P1 safety boundary:

- no new endpoint contract
- no ORM
- no MemoryManager
- no Embedding or vector store
- no Tool Registry
- no multi-agent workflow
- no Web UI
- no user or permission system
- no diagnosis, prescription, or treatment-plan output

Reports:

- `docs/P1_4_API_STABILITY_REPORT.md`
- `docs/P1_4_API_CONTRACT_GATE_REPORT.md`

## P1.5 Report Snapshot, Auditability, Traceability

P1.5 adds persisted final-report snapshots and lightweight auditability on top
of the existing SQLite persistence layer. It stores each generated report in a
new `reports` table with the current `state_version`, redacted `report_json`,
and redacted `safety_flags_json`.

P1.5 keeps the P1.1 success response contract stable:

- `/health` remains the exact P1.1 contract
- top-level API response fields are unchanged
- `state.state_version` is additive
- P1.2 session/state/turn recovery still works after cache clear
- P1.3 `schema_meta` remains compatible with the P1.4 gate

P1.5 adds:

- `app/api/report_audit.py`
- `scripts/audit_session.py`
- `tests/test_p1_5_report_audit.py`
- `tests/test_p1_5_report_snapshot.py`
- `docs/P1_5_REPORT_AUDITABILITY_REPORT.md`
- `artifacts/p1_5_report_auditability.json`

P1.5 remains inside the P1 safety boundary:

- no ORM
- no MemoryManager
- no Embedding or vector-store expansion
- no Tool Registry
- no multi-agent workflow
- no Web UI
- no user or permission system
- no diagnosis, prescription, or treatment-plan output

Report: `docs/P1_5_REPORT_AUDITABILITY_REPORT.md`.

## P1.6 Local Gate Automation And Secret Scan

P1.6 formalizes local validation. It adds a single gate runner and a reusable
secret scan script without changing API behavior or business capability.

P1.6 adds:

- `scripts/run_p1_gate.py`
- `scripts/secret_scan.py`
- `tests/test_p1_6_gate_runner.py`
- `tests/test_p1_6_secret_scan.py`
- `docs/P1_6_GATE_AUTOMATION_REPORT.md`
- `artifacts/p1_gate_result.json`
- `artifacts/secret_scan_result.json`

Gate command:

```powershell
python scripts/run_p1_gate.py --output artifacts/p1_gate_result.json
```

Observed P1.6 gate result:

- status: `ok`
- total checks: 13
- passed: 13
- failed: 0
- secret scan: `ok`, findings `0`, allowed synthetic test findings `10`
- recommendation: proceed to P1 Final Gate

P1.6 remains inside the P1 safety boundary:

- no ORM
- no MemoryManager
- no Embedding or vector-store expansion
- no Tool Registry
- no multi-agent workflow
- no Web UI
- no user or permission system
- no diagnosis, prescription, or treatment-plan output

Report: `docs/P1_6_GATE_AUTOMATION_REPORT.md`.

## P1 Final Gate

P1 Final Gate summarizes and verifies the complete P1 baseline.

Final gate artifacts:

- `docs/P1_FINAL_GATE_REPORT.md`
- `artifacts/p1_final_gate.json`

Observed status:

- P1 final gate: `ok`
- P1 gate runner: `ok`, 13/13 checks
- full unittest discovery: 132 tests OK
- secret scan: `ok`, findings `0`
- replay: `ok`, report snapshots `3`
- inspect/audit: `ok`
- `git diff --check`: exit code `0`

Recommendation: proceed to P2.0 baseline.

## P2.0 Baseline

P2.0 freezes the passed P1 baseline and adds documentation/artifacts for the
next phase:

- `docs/API_CONTRACT.md`
- `docs/SQLITE_SCHEMA.md`
- `docs/SAFETY_BOUNDARY.md`
- `docs/P2_BASELINE.md`
- `artifacts/p2_baseline.json`

P2.0 does not add P2.1+ capability. It keeps the P1 API contract and safety
boundary unchanged.

The current P1 to P2 engineering path is documented in
`docs/P1_TO_P2_ENGINEERING_ROADMAP.md`.

## P2 Final Gate Index Addendum

P2 Final Gate is now complete and passed.

Primary P2 final artifacts:

- `docs/P2_FINAL_REPORT.md`
- `artifacts/p2_final_gate.json`
- `artifacts/p2_gate_result.json`

Observed status:

- P1 gate: `ok`, 13/13 checks
- P2 gate: `ok`, 6/6 checks
- full unittest discovery: 191 tests OK
- case corpus eval: `ok`, 12/12 cases
- long-session reliability: `ok`, 3 sessions x 50 turns
- replay/inspect/audit: `ok`
- secret scan: `ok`, findings `0`
- `git diff --check`: exit code `0`

Recommendation: proceed to P3.0 while preserving the current safety and product
boundary.
