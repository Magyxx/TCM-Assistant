# Phase 6C Source Governance Validation

Generated: 2026-06-22

## Scope

P6C validates source registry governance, source review, runtime source gating, expanded retrieval evaluation, RAG injection defenses, source poisoning fail-closed behavior, and evidence metadata audit records.

## Entrypoints

```bash
python scripts/run_p6c_source_review.py
python scripts/run_p6c_source_registry_validation.py
python scripts/run_p6_knowledge_pipeline.py
python scripts/run_p6b_runtime_rag_validation.py
python scripts/run_p6c_retrieval_eval.py
python scripts/run_p6c_gate.py
```

## Artifacts

P6C writes:

- `artifacts/p6c_source_review.json`
- `artifacts/p6c_source_registry_validation.json`
- `artifacts/p6c_retrieval_eval.json`
- `artifacts/p6c_evidence_metadata_audit.jsonl`
- `artifacts/p6c_gate_report.json`
- `knowledge/eval/p6c_retrieval_safety_eval.json`

P6/P6B artifacts remain valid:

- `artifacts/p6_knowledge_pipeline.json`
- `artifacts/p6b_runtime_rag_validation.json`
- `artifacts/p6b_runtime_rag_trace_samples.json`
- `knowledge/processed/p6_chunks.jsonl`
- `knowledge/indexes/p6_bm25_index.json`

## Required Metrics

The gate expects:

| Metric | Expected |
| --- | --- |
| `p6c_gate_status` | `ok` |
| `source_registry_schema_pass` | `true` |
| `approved_for_runtime_count` | `>= 1` |
| `unknown_rights_loaded_count` | `0` |
| `unknown_provenance_loaded_count` | `0` |
| `failed_safety_loaded_count` | `0` |
| `pii_source_loaded_count` | `0` |
| `smoke_only_source_loaded_count` | `0` |
| `runtime_index_loaded` | `true` |
| `chunk_schema_pass` | `true` |
| `retrieval_eval_case_count` | `>= 30` |
| `retrieval_eval_pass_rate` | `>= 0.90` |
| `critical_risk_retrieval_recall` | `1.0` |
| `rag_boundary_pass` | `true` |
| `core_state_mutation_count_by_rag` | `0` |
| `rag_injection_followed_count` | `0` |
| `hallucinated_citation_count` | `0` |
| `diagnosis_or_prescription_violation_count` | `0` |
| `report_safety_violation_count` | `0` |
| `evidence_audit_schema_pass` | `true` |
| `trace_schema_pass` | `true` |
| `all_json_artifacts_valid` | `true` |

## Test Coverage

P6C adds:

- `tests/test_p6c_source_registry.py`
- `tests/test_p6c_source_review.py`
- `tests/test_p6c_retrieval_eval.py`
- `tests/test_p6c_rag_injection.py`
- `tests/test_p6c_source_poisoning.py`
- `tests/test_p6c_evidence_audit.py`

These tests cover registry schema, independent training permission, smoke-only exclusion, unknown-rights fail-closed behavior, expanded retrieval thresholds, RAG injection boundary, PII source rejection, chunk/source hash mismatch, stale-index warning hooks, and audit schema completeness.

## Current Validation Summary

The current source registry contains two sources: one smoke-only fixture excluded from runtime and one internal synthetic policy fixture approved for runtime/eval. Training and public demo permissions remain false.

The current retrieval eval has 32 cases and covers all requested categories. No real medical book text, private patient content, or long-term patient memory is ingested.

## Known Cautions

- `scripts/run_p6c_source_review.py` may report `status=caution` because the smoke-only fixture has unknown rights/provenance by design and is explicitly fail-closed. The P6C gate treats this as acceptable because no review failures exist and at least one runtime-approved source is available.
- The P6C gate keeps embedded P5 regression deterministic by disabling the real LLM probe. Run `python scripts/run_p5_real_runtime_validation.py` separately for real provider availability.
- Some optional ML libraries emit PyTorch/transformers warnings in this environment; hard gates remain the blocker.

## P7 Recommendation

Next work should focus on rights-cleared source acquisition, reviewer workflow UX, source removal/rebuild operations, optional database persistence for evidence metadata, and a larger retrieval evaluation corpus.
