# Phase 4 Freeze Report

Generated: 2026-06-20

Phase 4 is frozen as a code-health, boundary, compatibility, and stability
milestone. The project is ready to enter P5 real-path validation, with P5
explicitly scoped as runtime-path verification rather than another code-health
cleanup phase.

## product_positioning_freeze

TCM-Assistant remains a Chinese medicine consultation-information assistant.
It organizes interview information, highlights risk signals, and produces
structured summaries. It does not diagnose, prescribe, recommend treatment
plans, or replace clinician judgment.

Frozen safety boundary:

> 本系统仅用于问诊信息整理和风险提示，不构成诊断或治疗建议，不能替代医生判断。如出现持续高热、胸痛、呼吸困难、便血、意识异常、剧烈腹痛等高风险信号，应及时线下就医。

## completed_phase4_work

| Subphase | Status | Result |
| --- | --- | --- |
| P4.6.0 Code Health Audit | complete | Audited code health, dependencies, complexity, duplicate logic, dead-code candidates, architecture risks, and test gaps without changing runtime behavior. |
| P4.6.1 Safe Hygiene | complete | Added dev-only requirements and removed narrow unused imports/duplicate import; no schema/API/SQLite/risk behavior changes. |
| P4.6.2 Code Health Gate Baseline | complete | Added repeatable hard/soft code-health gate with hard checks blocking and soft findings advisory. |
| P4.6.3 Soft Tool Adoption | complete | Installed dev-only tools and recorded real soft baseline for ruff, mypy, vulture, radon, deptry, and pytest. |
| P4.6.4 Structural Cleanup | complete | Consolidated duplicate gate redaction helper into `scripts/gate_utils.py`, preserving script compatibility aliases. |
| P4.6.5 Deprecation & Compatibility Plan | complete | Inventoried legacy, gate, SFT, RAG, demo, eval, and artifact entrypoints; no deletion performed. |
| P4.6.6 Encoding / Chinese Literal Stability | complete | Canonicalized the safety boundary, repaired one low-risk mojibake script sample, and added golden tests. |
| P4.6.7 Phase 4 Freeze Report | complete | Added this final freeze report and `artifacts/phase4_freeze_summary.json`. |

## hard_gate_results

Latest hard gate from `python scripts/run_code_health_gate.py`:

| Check | Status | Notes |
| --- | --- | --- |
| compileall | pass | `app`, `scripts`, and `tests` compile. |
| P4 gate | pass | P4 gate exits successfully. |
| unittest | pass | 273 tests passed. |
| baseline JSON validity | pass | `artifacts/code_health_gate_baseline.json` is valid JSON. |

Hard gate status: `ok`.

Final P4.6.7 validation:

| Command | Status | Notes |
| --- | --- | --- |
| `python scripts/run_code_health_gate.py` | pass | hard=`ok`, soft=`caution`, hard checks 4/4. |
| `python scripts/run_p4_gate.py` | pass | Existing Transformers/PyTorch advisory remains non-blocking. |
| `python -m unittest discover -s tests` | pass | 273 tests passed. |
| `python -m compileall -q app scripts tests` | pass | Compile check passed. |
| `python -m json.tool artifacts/phase4_freeze_summary.json` | pass | Final JSON syntax check passed. |

## soft_tool_baseline_summary

Soft tools are installed through `requirements-dev.txt` and are not part of
runtime `requirements.txt`.

| Tool | Status | Summary |
| --- | --- | --- |
| ruff check | caution | 67 historical findings remain after one safe fix; mostly script bootstrap `E402`, one compatibility import, and unused variable candidates. |
| ruff format | caution | 112 files would be reformatted in the latest gate run; broad formatting remains out of scope. |
| mypy | caution | Stops on duplicate module mapping for `scripts/audit_session.py`; needs config/package-base review. |
| vulture | caution | 5 candidates remain; current findings are not safe to remove without semantic review. |
| radon | ok/advisory | 657 blocks analyzed, average complexity A; high-complexity candidates remain registered. |
| deptry | caution | 6 dependency findings require runtime/SFT/RAG compatibility review. |

Soft findings are classified and recorded as `safe_fix_now`,
`keep_with_reason`, `caution_review_later`, and `risky_do_not_touch` in
`artifacts/code_health_soft_tools.json`.

## test_status

Current validation: `python -m unittest discover -s tests` passed with 273 tests.

The P4 exit criterion referenced 268 tests. The count increased because later
P4.6 cleanup added focused tests:

- P4.6.4 added `tests/test_p4_6_gate_utils.py`.
- P4.6.6 expanded Chinese literal/report-safety golden coverage.

The increase is intentional and does not reflect a reduced test scope.

## api_contract_status

Status: frozen.

Latest P4 gate reports:

- `api_contract_status=frozen`
- `api_response_body_changed=false`
- `api_version=v1`
- public API contract checks pass

No FastAPI route contract or response schema was changed in P4.6.7.

## sqlite_schema_status

Status: unchanged.

Latest P4 gate reports:

- `sqlite_schema_changed=false`
- `schema_version=1`
- `schema_stage=P1.3`

No SQLite table, column, or schema metadata migration was performed.

## pydantic_schema_status

Status: frozen.

`TurnOutput`, `RunState`, and `FinalReport` fields and semantics are unchanged.
P4.6.6 normalized a safety-boundary text value, but did not change any Pydantic
field, required/optional status, type, or schema meaning.

## risk_rule_semantics_status

Status: unchanged.

Risk rule IDs, keyword semantics, negation handling, and high-risk sticky
behavior were not modified. Vulture-reported `previous_status` remains a
review-later item, not a deletion target.

## rag_boundary_status

Status: frozen and passing.

P4 gate reports `p4_3_rag_boundary` passing with evidence metadata present.
RAG remains evidence/support only and cannot rewrite core consultation state:

- `chief_complaint`
- `duration`
- `risk_status`
- `risk_rule_ids`
- `risk_flags`

No large real knowledge base import was performed.

## legacy_compatibility_status

Status: retained with plan.

P4.6.5 inventoried legacy MVP/stateful/report CLI, gate runners, SFT/LoRA
manual path, RAG compatibility modules, demo/eval utilities, and artifacts.
No legacy, gate, SFT, or RAG compatibility entrypoint was deleted. Future
removal requires zero-reference proof, passing gates, replacement docs, and
human approval.

## encoding_status

Status: stabilized for key outputs.

P4.6.6 canonicalized runtime safety boundary text across API/report paths,
repaired low-risk mojibake in `scripts/validate_p1_api_contract.py`, and added
golden tests for UTF-8-sensitive literals and runtime safety metadata.

Known caution: current and historical gate artifacts may still contain captured
stdout mojibake in `stdout_tail`; this is recorded, not hand-edited.

## known_cautions

- Soft checks remain advisory and currently report historical lint/type/dependency findings.
- P4 gate and tests may emit the existing Transformers/PyTorch warning because Transformers expects PyTorch >= 2.4 while the environment has 2.1.0.
- Root-level `python -m unittest discover` can discover 0 tests; canonical command is `python -m unittest discover -s tests`.
- Some gate artifact `stdout_tail` fields still contain captured mojibake.
- Several high-complexity functions remain registered for future review.
- Legacy/deprecated candidates remain present until a later approved cleanup phase.
- `app/rag/build_vector_store.py` remains an experimental/archive candidate with optional dependency concerns.

## not_yet_done

- No P5 real LangGraph/LLM/RAG runtime-path validation has been started.
- No production deployment readiness claim is made.
- No broad `ruff format` or mass lint cleanup has been applied.
- No large real Chinese medicine corpus has been imported.
- No legacy/SFT/RAG compatibility entrypoint has been deleted.
- No mypy package-base configuration has been finalized.
- No dependency lock/constraints file has been created.

## P5_entry_criteria

| Criterion | Status | Notes |
| --- | --- | --- |
| Hard gate all pass | met | `python scripts/run_code_health_gate.py` passes. |
| P4 gate passes | met | `python scripts/run_p4_gate.py` passes. |
| Test suite passes | met | 273 tests pass; count increase is explained above. |
| Soft baseline exists | met | Real soft-tool baseline exists with classified findings. |
| API contract frozen | met | P4 gate confirms frozen API contract. |
| SQLite schema unchanged | met | P4 gate confirms unchanged schema. |
| Pydantic schema semantics unchanged | met | `TurnOutput`, `RunState`, `FinalReport` unchanged. |
| Risk rule semantics unchanged | met | No risk-rule changes in P4.6.7. |
| Compatibility entrypoints planned | met | P4.6.5 deprecation plan exists. |
| Chinese literal/mojibake inventory exists | met | P4.6.6 report and artifact exist. |
| P5 scope separated from code health | met | P5 is real runtime-path validation, not P4 cleanup. |

P5 readiness: ready with cautions. No P5 blockers remain.

## recommended_P5_tasks

1. Run real-path validation with explicit environment capture for LangGraph,
   extractor mode, LLM settings, and RAG enablement.
2. Validate real LLM extraction on small approved smoke cases without expanding
   medical scope.
3. Validate real RAG evidence retrieval on the current tiny knowledge base; do
   not import large copyrighted or clinical corpora in the first P5 pass.
4. Compare fake/fallback/real paths without mixing their artifacts or states.
5. Capture latency, errors, redaction, safety boundary presence, and report
   validator results for each real-path run.
6. Keep `TurnOutput`, `RunState`, `FinalReport`, FastAPI contract, SQLite
   schema, and risk rules frozen unless a separate versioned change is approved.
