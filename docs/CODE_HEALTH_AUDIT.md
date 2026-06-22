# Code Health Audit

Generated: 2026-06-20T09:09:47+08:00

## Scope

本轮只做审计，不删除代码、不改业务逻辑、不改变外部 API 行为。

已扫描：

- `app`
- `scripts`
- `tests`
- `docs`
- `artifacts`
- `README.md`
- `requirements.txt`

保护边界：

- 不删除仍被 README、docs、tests、scripts、FastAPI route、workflow graph、tool registry 引用的代码。
- 不删除历史 gate 所需文件。
- 不改变现有 API response schema。
- 不改变 `TurnOutput`、`RunState`、`FinalReport` 语义。
- 不把 fake/test path 与 real runtime path 直接混合清理。

必备栏目映射：

- `unused imports / obvious lint issues`: see "Unused Imports / Obvious Lint Issues"
- `dead_code_candidates`: see "Dead Code Candidates"
- `duplicate_logic_candidates`: see "Duplicate Logic Candidates"
- `deprecated_interfaces`: see "Deprecated Interfaces"
- `architecture_boundary_violations`: see "Architecture Boundary Violations"
- `high_complexity_functions`: see "High Complexity Functions"
- `dependency_issues`: see "Dependency Issues"
- `test_gaps`: see "Test Gaps"
- `recommended_cleanup_plan`: see "Recommended Cleanup Plan"

## Evidence

工具与命令结果：

| Check | Result | Notes |
| --- | --- | --- |
| `python -m ruff --version` | unavailable | 当前环境未安装 ruff。 |
| `python -m mypy --version` | unavailable | 当前环境未安装 mypy。 |
| `python -m vulture --version` | unavailable | 当前环境未安装 vulture。 |
| `python -m radon --version` | unavailable | 当前环境未安装 radon。 |
| `python -m deptry --version` | unavailable | 当前环境未安装 deptry。 |
| `python -m pytest --version` | unavailable | 当前环境未安装 pytest；README 也说明当前 gate 使用 `unittest`。 |
| `python -m compileall -q app scripts tests` | pass | 语法编译通过。 |
| `python -m unittest discover -s tests` | caution | 输出显示 `Ran 268 tests in 235.921s` / `OK`，但外层命令最终返回 timeout code 124，说明全量测试进程退出或输出收尾存在稳定性问题。 |
| `python scripts/check_p0_env.py --json` | pass | 依赖探测为 `real-ready`。 |
| `python scripts/run_p4_gate.py --json ...` | pass | P4 gate 9/9 通过；API contract frozen，SQLite schema unchanged，boundary violations empty。 |
| AST import graph | pass | `app`/`scripts` 内部未发现循环依赖。 |

扫描规模：

- Python files scanned: 131
- Text/reference files scanned: 250
- AST parse errors: 0
- Internal import cycles: 0

## Executive Summary

当前项目主风险不是明显的“可以直接删的大块死代码”，而是 P0-P4 演进后遗留的兼容入口、gate 脚本、旧实验链路、重复工具函数和高复杂度函数。由于大量文件被历史 baseline、gate、README、docs 或 tests 引用，第一轮不建议做删除式清理。

最适合第一批处理的是 safe lint 和 dev-tooling：补 dev requirements、跑 ruff/mypy/vulture/radon/deptry 的固定命令、清理确认为非 re-export 的未使用导入、把重复 gate helper 收口到脚本工具模块。

需要谨慎处理的是 legacy/SFT/RAG 旧路径、`DEFAULT_DB_PATH` 这类“看似未用但被外部模块当 re-export 使用”的符号，以及任何会影响 `TurnOutput`、`RunState`、`FinalReport`、API response body、SQLite schema、P4 gate artifact 的改动。

## Unused Imports / Obvious Lint Issues

| Risk | Candidate | Evidence | Recommendation |
| --- | --- | --- | --- |
| caution | `app/api/sqlite_store.py:13` imports `DEFAULT_DB_PATH` | AST shows unused inside `sqlite_store.py`, but `scripts/run_case_corpus_eval.py` imports `DEFAULT_DB_PATH` from `app.api.sqlite_store`. | Do not simply remove. First migrate callers to `app.api.runtime_config.DEFAULT_DB_PATH` or declare an explicit compatibility re-export with a comment. |
| safe | `app/chains/sft_infer_chain.py:3` imports `Path` | No AST usage. | Remove after focused import test for SFT module. |
| safe | `app/chains/sft_infer_chain.py:7` imports `PeftModelForCausalLM` | No AST usage; `PeftModel` is used. | Remove after focused SFT import test. |
| safe | `scripts/audit_session.py:6` imports `sqlite3` | No AST usage. | Remove after `python -m py_compile scripts/audit_session.py`. |
| safe | `scripts/run_long_session_demo.py:11` imports `Optional` | No AST usage. | Remove after py_compile and long-session script test. |
| safe | `app/chains/report_chain.py:22` re-imports `TurnOutput` after line 9 block import | Duplicate import; no schema behavior change. | Remove duplicate import only. |
| caution | Several files contain visibly mojibake Chinese literals, for example `app/api/models.py`, `app/chains/report_chain.py`, `app/graphs/consultation_nodes.py`, `app/rag/*`. | User-visible text and snapshots may currently depend on these literals. | Do not repair in this audit round. Create a separate encoding normalization plan with API snapshot/gate tests before changing strings. |
| safe | Formatting irregularity in `app/rag/bm25_retriever.py` around `EvidenceChunk(...)` construction | Compile passes but indentation is hard to read. | Auto-format only after ruff/black configuration is added; verify P4 RAG tests. |

## Dead Code Candidates

These are candidates for human review, not deletion approvals.

| Risk | Candidate | Evidence | Recommendation |
| --- | --- | --- | --- |
| caution | `app/schemas/consultation.py::ConsultationResult` | Low reference count; not imported by app/tests/scripts in scan. | Mark deprecated first or add an owner note; remove only after README/docs/tests scan confirms no planned use. |
| caution | `app/rag/build_vector_store.py` | Low reference score; not part of current P4 gate path; imports dense vector deps not listed in requirements. | Treat as experimental/vector-store utility. Either document as manual script with dependencies or move behind explicit experimental docs. Do not delete without approval. |
| caution | `app/chains/mvp_chain.py` + `scripts/run_mvp.py` | Low app references but `scripts/run_mvp.py` imports it; README lists project scripts. | Candidate for deprecation notice, not immediate removal. |
| caution | `app/chains/stateful_chain.py`, `app/chains/stateful1_chain.py`, `scripts/run_state.py`, `scripts/run_state1.py`, `app/prompts/stateful*.py` | Legacy stateful entrypoints are outside current API/P4 path but directly referenced by scripts. | Add a `legacy/` inventory or deprecation table; keep until docs and scripts are migrated. |
| caution | `app/agentic/workflow_adapter.py::P4WorkflowResult` | Dataclass exists but current adapter returns a plain dict. | Either use it as an internal typed envelope in a behavior-preserving way or remove in a dedicated cleanup after P4 tests. |
| caution | `app/api/sqlite_store.py::insert_report_snapshot` and `fetch_latest_report_for_session` | Low current references; persistence helper API may be reserved for report history. | Add tests if these are intended public helpers; otherwise deprecate before removal. |
| caution | `scripts/filter_sft_manual_only.py`, `scripts/test_sft_chain.py`, `scripts/test_sft_lora_infer.py` | README and SFT docs reference SFT workflow scripts. | Keep as manual SFT tooling unless SFT docs are retired. |
| risky | Historical docs/artifacts under `docs/P*_*.md`, `artifacts/p*_*.json` | Many are baseline/gate evidence. | Do not delete in cleanup waves unless a new archival policy explicitly permits it. |

## Duplicate Logic Candidates

| Risk | Candidate | Evidence | Recommendation |
| --- | --- | --- | --- |
| caution | BM25 tokenization / boost logic duplicated in `app/rag/rag_retriever.py` and `app/rag/bm25_retriever.py` | Both define `COMMON_TERMS`, `normalize_text`, `tokenize`, `extract_main_complaint_terms`, `score_boost`. | Prefer extracting shared pure helpers only after snapshotting current RAG rankings. Keep `rag_retriever.py` compatibility if README/docs still list it. |
| caution | JSON-object extraction duplicated across `app/chains/report_chain.py`, `app/chains/turn_extractor.py`, `app/chains/sft_infer_chain.py`, and SFT test scripts | Similar brace/fenced-code parsing logic appears in multiple places. | Create a shared parser utility with characterization tests before swapping callers. |
| safe | `_redact_preserving_schema` duplicated in `scripts/run_p2_gate.py`, `scripts/run_p3_gate.py`, `scripts/run_p4_gate.py` | Exact duplicate function body found by AST. | Move into `scripts/gate_utils.py` after adding/adjusting gate tests. |
| safe | `_configured_db` duplicated in `scripts/run_case_corpus_eval.py` and `scripts/run_long_session_demo.py` | Exact duplicate function body found by AST. | Move to a small script helper if both scripts remain active. |
| safe | `_boundary_check` duplicated in `scripts/run_case_corpus_eval.py` and `scripts/run_p2_gate.py` | Exact duplicate function body found by AST. | Extract only if it reduces gate drift; keep output shape unchanged. |
| caution | Fallback graph logic in `app/graphs/consultation_nodes.py` mirrors core `report_chain` functions | This is intentional fallback around optional/fragile legacy imports. | Do not merge blindly. First define whether fallback must preserve old behavior when `report_chain` import fails. |

## Deprecated Interfaces

| Risk | Interface | Evidence | Recommendation |
| --- | --- | --- | --- |
| caution | `scripts/eval_report.py` `mode="legacy"` / `app.chains.report_chain.run_turn` | Legacy mode remains in eval script and report chain. | Keep until eval docs no longer require legacy comparison; mark in docs as compatibility path. |
| caution | `RunState.summary` and `TurnOutput.summary` compatibility fields | `docs/report_current_rules.md` says these are compatibility/process fields and should not be deleted yet. | Do not remove; any change must preserve Pydantic schema and API body. |
| caution | `fake` extractor exposed in `app/api/models.py::ExtractorMode` | Fake path is an API-visible mode, not only a test helper. | Removing or hiding this is an API schema change. If production policy changes, add versioned contract/gate first. |
| safe | README P3 gate note drift | `README.md` still says there is no `scripts/run_p3_gate.py`, while P3/P4 docs and file tree show it exists. | Documentation cleanup is safe if it preserves historical docs; update README current-status section only. |
| caution | Legacy MVP/stateful scripts | Present as direct scripts but not current P4 runtime path. | Add a deprecation inventory before moving/removing. |

## Architecture Boundary Violations

No hard internal import cycles were found, and the P4 gate reported:

- `api_contract_status=frozen`
- `api_response_body_changed=false`
- `sqlite_schema_changed=false`
- `boundary_violations=[]`

Boundary risks to track:

| Risk | Boundary | Evidence | Recommendation |
| --- | --- | --- | --- |
| caution | `app/api/state_validator.py` combines pure state validation with SQLite-backed session consistency helpers | It imports `connect` and `initialize_database` from `app.api.sqlite_store`. | Consider splitting pure schema validation from persistence consistency checks to reduce coupling. |
| caution | `app/rag/build_vector_store.py` places dense/vector-store experimental tooling in runtime package | It imports FAISS/vector-store dependencies not in requirements and writes `app/rag/faiss_index`. | Document as manual experimental path or isolate under scripts/experimental; do not touch current BM25/P4 RAG path. |
| caution | `app/graphs/consultation_nodes.py::generate_report` rebuilds evidence pack instead of reusing the pack produced by `retrieve_knowledge` | Potential repeated retrieval and inconsistent metadata if retriever behavior changes. | Characterize output first; then pass the existing pack through state if behavior must remain stable. |
| risky | Changing fake/fallback/real extractor availability | API request schema includes `real_llm`, `fake`, `fallback`; tests and gates use fake/fallback. | Do not remove or reinterpret without API versioning and gate updates. |
| caution | SFT inference dependency path lives in `report_chain` compatibility mode | `report_chain` optionally imports SFT; SFT packages are heavy and version-sensitive. | Keep optional import boundary; consider moving SFT-only code behind a clearer adapter later. |

## High Complexity Functions

Cyclomatic-style AST score threshold used: `complexity >= 10` or `loc >= 80`.

| Risk | Function | Complexity / LOC | Recommendation |
| --- | --- | --- | --- |
| caution | `scripts/run_case_corpus_eval.py::_evaluate_case` | 73 / 296 | Split reporting/calculation helpers after snapshotting artifact shape. |
| risky | `app/chains/report_chain.py::merge_turn_fields` | 46 / 166 | Main state merge logic; do not refactor without characterization tests around negation, risk sticky behavior, symptoms status, and final report generation. |
| caution | `app/api/state_validator.py::validate_state` | 32 / 87 | Split pure field validators; preserve error payload schema. |
| caution | `app/rag/rag_retriever.py::score_boost` | 31 / 78 | Legacy RAG path; consolidate only after ranking tests. |
| caution | `app/rag/bm25_retriever.py::score_boost` | 31 / 42 | Current BM25 path; consolidate with tests. |
| caution | `scripts/validate_p1_api_contract.py::run_contract_gate` | 30 / 193 | Gate script; refactor only if artifact schema is locked by tests. |
| caution | `scripts/audit_session.py::audit_session` | 30 / 162 | Split DB read, report audit, and output assembly helpers. |
| caution | `scripts/check_api_contract.py::build_api_contract_check_payload` | 30 / 136 | Keep payload schema stable; extract helper functions. |
| caution | `app/api/report_validator.py::_validate_structure` | 28 / 53 | Split required fields, type checks, safety checks. |
| caution | `scripts/run_long_session_demo.py::run_long_session_demo` | 26 / 149 | Separate execution, persistence inspection, and artifact assembly. |
| caution | `app/utils/sft_postprocess.py::postprocess_turn_output` | 25 / 96 | SFT path; add focused tests before refactor. |
| caution | `app/chains/turn_extractor.py::extract_turn` | 16 / 57 | Central extractor mode router; preserve fake/fallback/real boundaries. |

## Dependency Issues

| Risk | Issue | Evidence | Recommendation |
| --- | --- | --- | --- |
| safe | Dev audit tools are absent | ruff/mypy/vulture/radon/deptry/pytest modules not installed. | Add a dev requirements file or documented local tooling command set. |
| caution | `app/rag/build_vector_store.py` imports `langchain_community` and `langchain_text_splitters`, absent from `requirements.txt` | Static import scan. | If this script is retained, add optional/vector dependencies or document manual install. |
| caution | FAISS runtime dependency is implicit | `FAISS` vector store usage usually needs FAISS package availability. | Add optional dependency note for vector build script. |
| caution | `transformers` / PyTorch compatibility mismatch | P4 gate stderr: PyTorch >= 2.4 required but current PyTorch is 2.1.0, so Transformers disables PyTorch. | Improve `check_p0_env.py` to validate versions, not just importability. |
| caution | Requirements are mostly unpinned | `requirements.txt` has broad package names. | For release/gate reproducibility, add constraints or a lock file. |
| safe | `uvicorn` is not imported by Python code | It is used by README/runbook server command. | Keep; not an unused dependency. |
| caution | `accelerate` and `sentencepiece` are not imported in app runtime | They are SFT/training-adjacent dependencies. | Keep if SFT remains supported; otherwise move to optional SFT requirements. |

## Test Gaps

| Risk | Gap | Evidence | Recommendation |
| --- | --- | --- | --- |
| safe | Static analysis tools are not in test/dev environment | Preferred tools unavailable. | Add dev tooling and a non-mutating audit command. |
| caution | Full `unittest discover` is slow/noisy and did not cleanly return before wrapper timeout | It printed 268 tests OK but command exited 124 after timeout. | Add a quiet full-test command, suppress excessive logs, and ensure all resources close cleanly. |
| caution | No explicit tests for dead-code candidates before removal | Low-reference files include legacy scripts and helpers. | Before deletion, add smoke/import tests or document deprecation and remove references first. |
| caution | RAG ranking behavior lacks snapshot tests for helper consolidation | Duplicate score/tokenize logic exists. | Add deterministic ranking fixtures before extracting shared helpers. |
| risky | Encoding repair lacks snapshot coverage | Mojibake strings appear in API/report/schema literals. | Add API/report snapshot tests around user-visible Chinese output before changing any literals. |
| caution | Dependency version checks are shallow | `check_p0_env.py` reports present while P4 gate warns PyTorch is disabled by Transformers. | Add version assertions for SFT/transformers/torch compatibility. |
| caution | `sqlite_store` helper API coverage is incomplete | `insert_report_snapshot` / `fetch_latest_report_for_session` low references. | Either add tests or deprecate in docs before cleanup. |

## Recommended Cleanup Plan

### Phase 1: Safe Hygiene

1. [safe] Add `requirements-dev.txt` or `docs` command section for `ruff`, `mypy`, `vulture`, `radon`, `deptry`, and `pytest`.
2. [safe] Remove confirmed non-re-export unused imports: `Path` / `PeftModelForCausalLM` in `sft_infer_chain.py`, `sqlite3` in `scripts/audit_session.py`, `Optional` in `scripts/run_long_session_demo.py`.
3. [safe] Remove duplicate `TurnOutput` import in `app/chains/report_chain.py`.
4. [safe] Update current README status that still says `scripts/run_p3_gate.py` does not exist.
5. [safe] Add a quiet audit command that runs compile, P4 gate, and selected static tools when available.

### Phase 2: Caution Cleanup

1. [caution] Replace accidental `DEFAULT_DB_PATH` re-export usage by migrating callers to `app.api.runtime_config.DEFAULT_DB_PATH`, or make the re-export explicit and tested.
2. [caution] Create `scripts/gate_utils.py` for duplicated gate helpers, preserving artifact schemas.
3. [caution] Create shared JSON extraction utility with tests, then migrate `report_chain`, `turn_extractor`, and SFT callers one at a time.
4. [caution] Add a legacy inventory for MVP/stateful/SFT scripts, with owner/status/keep-or-deprecate decisions.
5. [caution] Add dependency version checks to `check_p0_env.py`, especially `transformers` + `torch`.
6. [caution] Add deterministic RAG ranking tests before consolidating BM25 tokenization/boost logic.

### Phase 3: Risky / Requires Human Approval

1. [risky] Repair mojibake Chinese literals only after API/report snapshot tests and product copy review.
2. [risky] Remove or change `fake`/`fallback` API extractor modes only through versioned API contract and gate updates.
3. [risky] Refactor `report_chain.merge_turn_fields` only with characterization tests covering current `RunState` semantics.
4. [risky] Delete historical docs/artifacts only after an archival policy explicitly allows it.
5. [risky] Change `TurnOutput`, `RunState`, or `FinalReport` fields only through schema/version gates.

## First Cleanup PR Suggestion

Recommended first PR scope:

- Add dev tooling docs or requirements.
- Fix safe unused imports excluding `DEFAULT_DB_PATH`.
- Fix duplicate `TurnOutput` import.
- Fix README current-status drift.
- Add or document a quiet code-health command.

Do not include:

- Any deletion of historical docs/artifacts.
- Any schema/API response changes.
- Any state merge, extractor, RAG ranking, or report-generation refactor.
- Any encoding repair.
