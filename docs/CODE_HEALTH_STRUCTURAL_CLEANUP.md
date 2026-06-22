# P4.6.4 Structural Cleanup

Generated/refreshed: 2026-06-20

P4.6.4 performs one narrow, reversible structural cleanup based on the P4.6.3
soft-tool baseline: duplicate gate artifact redaction logic is consolidated into
a scripts-only helper. This keeps hard gates and soft reports separate, avoids
runtime behavior changes, and leaves API, schema, risk, RAG, SFT, and legacy
compatibility boundaries untouched.

## changed_files

| File | Change | Risk |
| --- | --- | --- |
| `scripts/gate_utils.py` | Added shared `redact_preserving_schema` helper for gate artifact redaction. | safe |
| `scripts/run_p2_gate.py` | Replaced duplicate private gate redaction helper with shared import alias. | safe |
| `scripts/run_p3_gate.py` | Replaced duplicate private gate redaction helper with shared import alias. | safe |
| `scripts/run_p4_gate.py` | Replaced duplicate private gate redaction helper with shared import alias. | safe |
| `tests/test_p4_6_gate_utils.py` | Added focused unit test for recursive gate payload redaction. | safe |
| `docs/CODE_HEALTH_STRUCTURAL_CLEANUP.md` | Added canonical P4.6.4 structural cleanup report. | safe |
| `artifacts/code_health_structural_cleanup.json` | Refreshed machine-readable P4.6.4 artifact. | safe |

## extracted_helpers

No core runtime helper was extracted in this phase. High-complexity functions
remain registered for later review because they touch state merge, report
validation, risk/RAG scoring, or long-running script behavior.

## merged_helpers

| Helper | From | To | Compatibility |
| --- | --- | --- | --- |
| Gate artifact redaction | `scripts/run_p2_gate.py`, `scripts/run_p3_gate.py`, `scripts/run_p4_gate.py` duplicate private helpers | `scripts/gate_utils.py::redact_preserving_schema` | Gate scripts keep `_redact_preserving_schema` import aliases, so local call sites and output behavior remain stable. |

## boundary_improvements

- Gate-only redaction logic now lives under `scripts/`, not inside `app/`.
- `app` does not import `scripts`; the application runtime remains independent
  from gate tooling.
- `app/rules`, `app/rag`, `app/memory`, and `app/agentic` have no FastAPI
  imports in the scanned files.
- RAG boundary checks remain read-only for core `RunState` fields:
  `chief_complaint`, `duration`, `risk_status`, and `risk_rule_ids`.
- No app schema, API contract, SQLite schema, or risk rule semantic boundary was
  changed.

## tests_added_or_updated

| Test | Purpose |
| --- | --- |
| `tests/test_p4_6_gate_utils.py` | Verifies recursive redaction across dict keys, nested lists, tuples, numeric keys, and serialized output. |

## risky_items_not_touched

- `TurnOutput`, `RunState`, and `FinalReport` fields and semantics.
- FastAPI request/response contract.
- SQLite tables, columns, and schema metadata.
- Risk rule IDs, keyword semantics, and sticky high-risk behavior.
- RAG evidence boundary and core state fields.
- Legacy MVP/stateful scripts, gate scripts, SFT scripts, and RAG compatibility
  modules.
- Runtime `requirements.txt`.
- User-visible Chinese literals and existing encoding/mojibake candidates.

## validation_results

| Command | Status | Notes |
| --- | --- | --- |
| `python scripts/run_code_health_gate.py` | pass | hard=`ok`, soft=`caution`, 4/4 hard checks passed. |
| `python scripts/run_p4_gate.py` | pass | Existing Transformers/PyTorch warning remains advisory. |
| `python -m unittest discover -s tests` | pass | 270 tests passed. |
| `python -m compileall -q app scripts tests` | pass | Compile check passed. |
| `python -m json.tool artifacts/code_health_structural_cleanup.json` | pass | P4.6.4 JSON artifact is valid. |

## remaining_complexity_candidates

These are recorded only. No unsafe split was attempted in P4.6.4.

| File | Symbol | Grade |
| --- | --- | --- |
| `app/chains/report_chain.py` | `merge_turn_fields` | F (47) |
| `scripts/run_case_corpus_eval.py` | `_evaluate_case` | F (76) |
| `app/api/state_validator.py` | `validate_state` | E (33) |
| `app/rag/bm25_retriever.py` | `score_boost` | E (32) |
| `app/rag/rag_retriever.py` | `score_boost` | E (32) |
| `scripts/check_api_contract.py` | `build_api_contract_check_payload` | E (33) |
| `scripts/run_long_session_demo.py` | `run_long_session_demo` | E (39) |
| `scripts/validate_p1_api_contract.py` | `run_contract_gate` | E (32) |
| `app/api/report_validator.py` | `_validate_structure`, `_validate_state_support` | D (30), D (24) |
| `app/api/state_validator.py` | `validate_session_consistency` | D (23) |
| `app/utils/sft_postprocess.py` | `postprocess_turn_output` | D (26) |

## next_recommended_phase

P4.6.5 Deprecation & Compatibility Plan:

- Inventory legacy, gate, SFT, and RAG compatibility entrypoints.
- Mark keep/deprecate candidates without deleting or moving them.
- Require human approval before any future removal.
