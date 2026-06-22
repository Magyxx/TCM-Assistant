# DEVICE2_REPO_INTAKE

## 1. Repository Source

* repo url: `https://github.com/Magyxx/TCM-Assistant.git`
* initial workspace: `C:\Users\Administrator\Documents\TCM-Ass`
* clone path: `C:\Users\Administrator\Documents\TCM-Ass\TCM-Assistant`
* clone note: the initial workspace contained an empty read-only `.git`, so the GitHub repository was cloned into the `TCM-Assistant` subdirectory.
* remote: `origin https://github.com/Magyxx/TCM-Assistant.git`
* current branch: `feature/device2-local-lora-extractor`
* target branch: `feature/device2-local-lora-extractor`
* latest main commit: `eefdfecf4e53cf196ce8815087533cf810919a07` (`docs: prepare device2 sft lora handoff`)
* latest tag: `v0.7.0-p7-caution`
* latest tag commit: `533cb38` (`freeze: P7 service storage memory tools observability gate`)

Observed intake commands:

```text
git status --short --branch
## feature/device2-local-lora-extractor

git remote -v
origin  https://github.com/Magyxx/TCM-Assistant.git (fetch)
origin  https://github.com/Magyxx/TCM-Assistant.git (push)

git log --oneline --decorate -n 20
eefdfec (HEAD -> feature/device2-local-lora-extractor, origin/main, origin/exp/sft-lora-extractor, origin/HEAD, main) docs: prepare device2 sft lora handoff
533cb38 (tag: v0.7.0-p7-caution) freeze: P7 service storage memory tools observability gate
6134244 (origin/sft-local-pipeline) add SFT LoRA local training and inference pipeline
d9bcae5 refactor(report): rename low-risk labels and add current rules doc
f23a780 init stable report baseline

git tag --sort=-creatordate | Select-Object -First 20
v0.7.0-p7-caution
```

## 2. Branch Topology

* main branch status: local `main`, `origin/main`, and the new Device2 branch all point to `eefdfec`.
* old branches found:
  * `remotes/origin/backup/main-before-p7-device1-20260622-e986065`
  * `remotes/origin/exp/sft-lora-extractor`
  * `remotes/origin/sft-local-pipeline`
* device2 branch status: `feature/device2-local-lora-extractor` was created from current `main`.
* ancestry check: `origin/main is ancestor of HEAD: yes`.
* branch safety conclusion: branch topology is clear. No old branch was modified, deleted, rebased, or force-updated.

## 3. Project Stage Understanding

* current project phase: P7 release freeze, with an additional `main` handoff commit for Device2 documentation.
* P7 freeze meaning: P7 is frozen as a functional-complete local baseline for service, storage, memory, tools, observability, safety, and gate layers. The frozen public API and safety boundary must be preserved.
* functional complete status: functional complete for the non-Docker local baseline.
* known caution/warning: `p7_gate_status=caution` because Docker CLI was unavailable on Device1. `artifacts/p7_docker_smoke.json` records `docker CLI not found`, `docker_runtime_available=false`, and `docker_smoke_pass=false`. This is an environment limitation, not a feature failure.
* current release boundary: inquiry information organization only. The system must not diagnose, prescribe, create treatment plans, replace clinicians, let RAG mutate core state, or let model output directly control high-risk triage.

## 4. Key Existing Capabilities

| Capability | Status | Evidence | Device2 relevance |
| --- | --- | --- | --- |
| FastAPI | yes | `app/api/main.py`, `app/api/models.py`, `docs/P7_API_REFERENCE.md` | Device2 must preserve stable endpoint bodies and use additive/internal surfaces for new backend details. |
| LangGraph runtime | yes | `app/graphs/consultation_graph.py`, P5 validation | Device2 extractor output enters the `extract_turn` node before validation and merge. |
| SQLite persistence | yes | `app/storage/sqlite_store.py`, `app/api/sqlite_store.py`, `docs/P7_STORAGE_SCHEMA.md` | Do not change schema during extractor work unless explicitly approved. |
| RAG | yes | `app/rag/`, `docs/P6B_RUNTIME_RAG_INTEGRATION.md`, `artifacts/p6b_gate_report.json` | RAG is evidence/report support only; Device2 LoRA must not use RAG to mutate core state. |
| risk rules | yes | `app/rules/risk_rules.py`, `risk_rule_check` graph node | High-risk status remains rule-first and outside LoRA authority. |
| safety boundary | yes | `docs/SAFETY_BOUNDARY.md`, `app/safety/report_safety.py`, validators | Device2 must keep no-diagnosis/no-prescription behavior. |
| eval gates | yes | `scripts/run_p1_gate.py` through `scripts/run_p7_gate.py`, `scripts/eval_report.py`, `scripts/eval_sft_extract.py` | Local LoRA evaluation should extend or align with existing gate/eval metrics, not replace them. |
| code health | yes | `scripts/run_code_health_gate.py`, `docs/CODE_HEALTH_GATE_BASELINE.md` | Existing hard gate is ok; soft cautions are advisory. |
| artifacts policy | yes | `docs/ARTIFACTS_POLICY.md`, `.gitignore` | Do not commit model weights, adapters, checkpoints, runs, private data, or `.env`. |
| API contract | frozen | `docs/API_CONTRACT_FREEZE.md`, `docs/API_CONTRACT.md` | Future backend switch must be introduced carefully; stable response bodies cannot be polluted. |

## 5. Key Files Read

| file path | exists | purpose | device2 relevance |
| --- | --- | --- | --- |
| `README.md` | yes | Current status, P7 caution, safety boundary, runtime notes, Device2 entry note. | Confirms P7 status and old `exp/sft-lora-extractor` guidance. |
| `.env.example` | yes | Local environment template. | Shows `TCM_LLM_MODE=fake`, storage/RAG paths, and secret/model artifact warnings. |
| `.gitignore` | yes | Excludes secrets, DBs, weights, LoRA adapters, checkpoints, outputs, caches. | Directly protects Device2 training outputs from accidental commit. |
| `requirements.txt` | yes | Runtime dependencies. | Already includes model/SFT-adjacent packages, but this phase does not install anything. |
| `requirements-dev.txt` | yes | Dev-only code-health tools. | Soft gate tools should stay development-only. |
| `pyproject.toml` | no | Not present. | No central tool config confirmed. |
| `pytest.ini` | no | Not present. | Tests use unittest discovery under `tests/`. |
| `docker-compose.yml` | yes | Docker API service wrapper. | Docker smoke is the only P7 caution. |
| `Dockerfile` | yes | Python 3.11 slim API image. | Confirms Docker entrypoint exists even though local Docker smoke was unavailable. |
| `docs/P7_RELEASE_FREEZE.md` | yes | P7 freeze source of truth. | Defines current baseline and caution. |
| `docs/P7_GITHUB_UPLOAD_CHECKLIST.md` | yes | Upload and validation checklist. | Lists files/artifacts to keep or exclude. |
| `docs/API_CONTRACT_FREEZE.md` | yes | Frozen public API contract. | Device2 backend work must not alter stable top-level response bodies. |
| `docs/ARTIFACTS_POLICY.md` | yes | Artifact retention/exclusion policy. | No model weights/adapters/checkpoints/private data in version control. |
| `docs/BRANCHING_POLICY.md` | yes | P7/P7.5/P8/SFT branch policy. | Records old SFT experiment branch and branch isolation rules. |
| `docs/P6B_FINAL_REPORT.md` | no | Requested historical report. | Not found; `docs/P6B_RUNTIME_RAG_INTEGRATION.md` and `docs/PHASE6B_RUNTIME_RAG_VALIDATION.md` were read instead. |
| `docs/P6B_RUNTIME_RAG_REPORT.md` | no | Requested historical report. | Not found; replacement P6B runtime RAG docs exist. |
| `docs/P5_FINAL_REPORT.md` | no | Requested historical report. | Not found; `docs/PHASE5_REAL_RUNTIME_VALIDATION.md` was read instead. |
| `docs/P4_FINAL_REPORT.md` | yes | P4 workflow/memory/RAG/tool registry summary. | Shows controlled agentic workflow layer without API/schema change. |
| `docs/P3_FINAL_RELEASE_CANDIDATE.md` | yes | P3.5 RC gate and frozen v1 contract. | Confirms stable endpoint set and non-goals. |
| `docs/P3_5_RC_GATE_REPORT.md` | yes | P3.5 gate result. | Confirms API/SQLite/safety stability at P3. |
| `docs/P2_FINAL_REPORT.md` | yes | P2 final gate and validators. | Confirms state/report validators and SQLite stability. |
| `docs/P1_GATE_REPORT.md` | yes | P1 gate history. | Confirms FastAPI and SQLite path emergence, though some text is mojibake. |
| `docs/P0_FINAL_BASELINE.md` | yes | P0 extraction/risk/RAG/safety baseline. | Confirms original TurnOutput-driven extraction and risk rules. |
| `docs/RELEASE_PACKAGING.md` | yes | Local reproducibility package. | Confirms runtime modes and secret policy. |
| `docs/CODE_HEALTH_GATE_BASELINE.md` | yes | Hard/soft code health gate. | Confirms risky items not to touch. |
| `docs/DEVICE2_ONBOARDING.md` | yes | Device2 old onboarding. | Useful, but old branch name differs from this task's target branch. |
| `docs/DEVICE2_CODEX_PROMPT.md` | yes | Previous Device2 prompt. | Confirms old `exp/sft-lora-extractor` scope. |
| `docs/sft_data_design.md` | yes | Existing SFT sample design. | Confirms training labels align with TurnOutput-style JSON. |
| `docs/sft_training_plan.md` | yes | Existing SFT/LoRA plan. | Confirms scripts exist but this phase must not train. |
| `app/api/` | yes | FastAPI service, models, routes, runtime/session layer. | Public API backend modes currently `real_llm`, `fake`, `fallback`. |
| `app/graphs/` | yes | LangGraph node sequence and fallback runner. | Device2 insertion point is before `validate_turn` and `merge_state`. |
| `app/rag/` | yes | Evidence retrieval, boundary, P6 runtime RAG. | Must remain read-only for core RunState. |
| `app/memory/` | yes | P7 memory layers and privacy checks. | Device2 must not bypass authoritative fact/risk behavior. |
| `app/tools/` | yes | P7 internal tool registry. | Risk/RAG/report tools remain deterministic support surfaces. |
| `app/storage/` | yes | P7 storage backend and schema. | Do not alter storage schema in D2-P0A. |
| `app/safety/` | yes | Report safety post-check. | LoRA cannot weaken report safety. |
| `app/agentic/` | yes | P4 workflow adapter. | Wraps existing flow; Device2 should not turn it into broad P8. |
| `app/config/` | no | Requested config directory. | Runtime config exists under `app/api/runtime_config.py`; no `app/config/` package found. |
| `scripts/run_p4_gate.py` | yes | P4 regression/boundary gate. | Existing gate should remain compatible. |
| `scripts/run_p3_gate.py` | yes | P3 RC gate. | Frozen API and delivery checks. |
| `scripts/run_code_health_gate.py` | yes | Code-health hard/soft gate. | D2 should not broad-fix soft cautions in this phase. |
| `scripts/check_release_packaging.py` | yes | Release packaging validation. | Helps keep reproducibility docs/artifacts consistent. |
| `scripts/run_p6b_gate.py` | yes | Runtime RAG aggregate gate. | Future eval should not break RAG boundary. |
| `scripts/run_p7_gate.py` | yes | P7 aggregate gate. | Current source of P7 caution/ok status. |
| `scripts/eval_report.py` | yes | Historical eval/report metrics. | Device2 eval metrics can align with its schema/risk/negation checks. |
| `scripts/eval_sft_extract.py` | yes | Existing SFT extraction evaluator. | Direct starting point for local_lora extraction metrics. |
| `tests/` | yes | Unit/regression tests across P0-P7. | Future Device2 tests should be focused and preserve existing semantics. |
| `artifacts/` | yes | Gate, eval, release, code health artifacts. | Source of truth for current baseline evidence. |

## 6. Main System Architecture Summary

TCM-Assistant is a structured inquiry assistant. It turns user symptom text into `TurnOutput`, validates and merges it into `RunState`, applies deterministic risk rules, optionally attaches read-only RAG evidence, and generates a safe `FinalReport`. P7 adds service, persistence, memory, tools, observability, and evidence/trace storage while preserving the stable v1 API response bodies.

```text
FastAPI API
  |
  v
ApiSession / session_runtime
  |
  v
P4WorkflowAdapter
  |
  v
LangGraph consultation_graph
  |
  +--> normalize_input
  +--> extract_turn_node
  |       |
  |       v
  |    app.chains.turn_extractor.extract_turn
  |       modes today: fake / real_llm / fallback
  |       output: TurnOutput
  |
  +--> validate_turn              (Pydantic TurnOutput)
  +--> merge_state                (RunState field merge)
  +--> risk_rule_check            (deterministic rule-first high-risk state)
  +--> decide_next / ask_followup
  +--> retrieve_knowledge         (P6B RAG, read-only for core state)
  +--> generate_report            (FinalReport)
  +--> safety_post_check          (no diagnosis / no prescription boundary)
  |
  v
RunState / FinalReport
  |
  +--> P7SQLiteStore: turns, run_states, risk_events, rag_evidence,
  |    final_reports, trace_events, audit_logs, memory_snapshots
  |
  +--> FastAPI stable responses + metadata/additive P7 endpoints
```

## 7. Device2 Insertion Point

The safest future insertion point is the extraction layer:

* `app/chains/turn_extractor.py::extract_turn`
* `app/graphs/consultation_nodes.py::extract_turn_node`
* `TurnOutput` schema validation in `app/schemas/report_schemas.py`

Future `local_lora_extractor` should behave like another extractor backend that returns `TurnOutput` JSON, then lets the existing graph continue:

```text
local_lora_extractor
  -> local vLLM OpenAI-compatible API
  -> base model + LoRA adapter
  -> JSON parse / repair / retry
  -> TurnOutput.model_validate(...)
  -> existing merge_state
  -> existing rule-first risk_rule_check
```

The current public API mode enum is `real_llm | fake | fallback`, while the Device2 target backend contract is `fake | cloud_llm | local_base | local_lora`. That mismatch should be handled in a later explicit branch/extractor contract phase, not silently changed in D2-P0A.

## 8. Do-Not-Touch List

* `app/schemas/report_schemas.py`: `TurnOutput`, `RunState`, `FinalReport` field semantics are frozen/risky.
* `app/api/models.py` and `app/api/main.py`: stable FastAPI response bodies and endpoint contract are frozen.
* `docs/API_CONTRACT_FREEZE.md`, `docs/P7_RELEASE_FREEZE.md`: freeze semantics must not be rewritten.
* `app/storage/sqlite_store.py` and `app/api/sqlite_store.py`: SQLite/P7 storage schema must not change casually.
* `app/rules/risk_rules.py`: high-risk semantics, negation handling, and rule IDs are rule-first and frozen/risky.
* `app/rag/*`: RAG boundary must remain read-only for core state.
* `app/safety/report_safety.py`, `app/api/report_validator.py`, `app/api/report_audit.py`: report safety must remain conservative.
* `tests/`: existing test semantics must not be relaxed for Device2.
* historical gate artifacts in `artifacts/`: preserve as baseline evidence.
* `.env.example`, `.gitignore`, `README.md`: do not modify in D2-P0A.
* old branches: do not modify, delete, rebase, or force-update `exp/sft-lora-extractor`, `sft-local-pipeline`, or backup branches.
* model artifacts: do not commit weights, adapters, checkpoints, training outputs, `wandb`, `mlruns`, caches, `.env`, secrets, local SQLite databases, or real patient/private data.

## 9. Risks and Unknowns

* Git ownership protection required `-c safe.directory=...` for local Git commands in this environment.
* The initial workspace root had an empty read-only `.git`; the actual repo lives in `TCM-Assistant/`.
* Requested files `docs/P6B_FINAL_REPORT.md`, `docs/P6B_RUNTIME_RAG_REPORT.md`, and `docs/P5_FINAL_REPORT.md` were not found. Equivalent/replacement phase docs were found and read.
* `pyproject.toml`, `pytest.ini`, and `app/config/` were not found.
* Existing Device2 docs mention `exp/sft-lora-extractor`, while this task explicitly created `feature/device2-local-lora-extractor`. This is documented and not treated as a blocker.
* Main currently contains existing SFT/LoRA scripts and processed data. D2-P0A did not run, install, train, or extend them.
* Some historical Chinese literals/docs are mojibake. This was observed only; literal repair is risky because it may change user-visible behavior or snapshots.
* Device2 hardware/WSL/CUDA/PyTorch/vLLM availability was not checked in this phase.
* Backend naming is not yet aligned: current API exposes `real_llm/fake/fallback`; target Device2 wants `fake/cloud_llm/local_base/local_lora`.

## 10. D2-P0A Acceptance Result

Result: `ok`

Rationale:

* Repository was obtained from GitHub.
* `main` and branch topology are clear.
* `feature/device2-local-lora-extractor` was created from latest `main`.
* Main project status, P7 freeze meaning, functional completeness, Docker-only caution, and core architecture are understood.
* Only allowed documentation/report files were added.
* No business code, tests, API contract, P7 freeze semantics, model artifacts, training data, or secrets were changed.

Non-blocking cautions are recorded in Section 9.

## Appendix A. Required Questions Answered

1. 当前项目主线完成到哪个阶段？P7 release freeze, with a newer Device2 handoff commit on `main`.
2. P7 freeze 的含义是什么？Functional-complete local baseline for service/storage/memory/tools/observability/safety/gates; public API and safety semantics are frozen.
3. 当前项目是否 functional complete？Yes for the non-Docker local baseline.
4. 当前 caution 或 warning 是什么原因导致的？Docker CLI unavailable, so Docker smoke could not run. It is not a feature failure.
5. 当前主系统核心能力有哪些？FastAPI, LangGraph runtime, Pydantic schemas, rule-first risk checks, SQLite/P7 storage, RAG evidence, memory, tool registry, observability, safety validators, gates.
6. 是否已有 FastAPI？Yes, `app/api/main.py`.
7. 是否已有 LangGraph runtime？Yes, `app/graphs/consultation_graph.py` with sequential fallback.
8. 是否已有 SQLite 持久化？Yes, P1/P7 SQLite layers and P7 storage schema.
9. 是否已有 RAG？Yes, BM25/P6B runtime RAG with evidence boundary.
10. 是否已有风险规则？Yes, `app/rules/risk_rules.py`.
11. 是否已有安全边界？Yes, docs plus report safety/audit/validator code.
12. 是否已有评估 gate？Yes, P1-P7 gate scripts and eval scripts.
13. 是否已有 code health gate？Yes, `scripts/run_code_health_gate.py`.
14. 是否已有 ExtractorBackend 或类似抽取层？There is a similar extraction layer in `app/chains/turn_extractor.py`, but no formal `ExtractorBackend` interface yet.
15. `TurnOutput`、`RunState`、`FinalReport` schema 在哪里？`app/schemas/report_schemas.py`.
16. 当前 LLM 调用路径在哪里？`app/chains/turn_extractor.py` for current graph extraction; legacy/report path also exists in `app/chains/report_chain.py`; old SFT path exists in `app/chains/sft_infer_chain.py`.
17. fake/fallback/real_llm 路径如何区分？API `ExtractorMode` is `real_llm | fake | fallback`; `extract_turn` routes fake to deterministic structured extraction, fallback to rule fallback, and real_llm to provider/native/tool/json-prompt strategies with rule fallback on failure.
18. 当前主系统哪些文件不能轻易改？Schemas, FastAPI response models/routes, API freeze docs, SQLite schemas, risk rules, RAG boundaries, safety/report validators, tests, gate artifacts, `.env.example`, README, P7 freeze docs.
19. 设备2支线应插入哪里？At the extraction layer before `validate_turn` and `merge_state`.
20. 设备2支线不应该碰哪些模块？Risk rules, RAG evidence authority, safety/report generation semantics, storage schema, frozen API top-level response bodies, historical tests/artifacts, old branches.
21. 后续 `local_lora_extractor` 最小接入点是什么？A function/backend adapter that calls local vLLM, returns `TurnOutput`, and reuses existing Pydantic validation and graph merge/risk nodes.
22. 训练数据最终要对齐哪个 schema？`TurnOutput` JSON, preferably through `SFTSampleOutput` that mirrors `TurnOutput`.
23. 评估指标如何衔接现有 eval？Extend `scripts/eval_sft_extract.py` and existing P5/P7 metrics with JSON valid rate, schema pass rate, field F1/accuracy, risk/negation metrics, fallback rate, latency.
24. 设备2支线如何避免与旧分支干扰？Use only `feature/device2-local-lora-extractor`, no force push/rebase/reset, no old branch modification, no model artifacts committed.
25. 是否建议把设备2训练产物合并回 main？No. Training outputs, weights, adapters, checkpoints, and runs should not merge into `main`; only reviewed code/docs/contracts/compact eval artifacts may be considered later with explicit approval.
