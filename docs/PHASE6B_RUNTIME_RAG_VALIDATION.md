# Phase 6B Runtime RAG Validation

Generated: 2026-06-21

## Goal

P6B validates that P6A knowledge artifacts are usable by the runtime RAG path without changing the consultation assistant's safety boundary. RAG can support impression, advice, explanation, evidence metadata, and traceability. It cannot rewrite core `RunState`, determine risk status, diagnose, prescribe, or replace clinician judgment.

## Validation Entrypoints

Focused runtime validation:

```bash
python scripts/run_p6b_runtime_rag_validation.py
```

Aggregate P6B gate:

```bash
python scripts/run_p6b_gate.py
```

The runtime validator executes four query classes:

- oral symptom wording;
- fixed risk terms;
- TCM/report terminology;
- report enhancement wording.

Each case retrieves evidence, attaches report references, checks RAG boundary, validates report safety, records trace fields, and writes audit rows.

## Artifacts

P6B writes:

- `artifacts/p6b_runtime_rag_validation.json`
- `artifacts/p6b_runtime_rag_trace_samples.json`
- `artifacts/p6b_rag_evidence_audit.jsonl`
- `artifacts/p6b_gate_report.json`

P6A artifacts remain:

- `artifacts/p6_knowledge_pipeline.json`
- `knowledge/processed/p6_chunks.jsonl`
- `knowledge/indexes/p6_bm25_index.json`
- `knowledge/eval/p6_retrieval_safety_eval.json`

All JSON artifacts are intended to pass `python -m json.tool`.

## Gate Schema

`artifacts/p6b_gate_report.json` uses this top-level structure:

```json
{
  "phase": "P6B",
  "status": "ok|caution|failed",
  "knowledge_pipeline": {},
  "runtime_rag": {},
  "rag_boundary": {},
  "safety": {},
  "trace": {},
  "regression": {},
  "artifacts": {},
  "failure_analysis": {}
}
```

The current implementation emits `ok` or `failed`. Real LLM availability remains tracked by the separate P5 validation script.

## Required Metrics

The P6B gate checks:

| Metric | Expected |
| --- | --- |
| `p6_knowledge_pipeline_status` | `ok` |
| `approved_source_count` | `>= 1` |
| `runtime_index_loaded` | `true` |
| `chunk_schema_pass` | `true` |
| `source_review_gate_pass` | `true` |
| `retrieved_evidence_count` | `> 0` |
| `retrieval_eval_pass_rate` | `1.0` |
| `rag_boundary_pass` | `true` |
| `core_state_mutation_count_by_rag` | `0` |
| `unapproved_source_loaded_count` | `0` |
| `smoke_only_source_loaded_count` | `0` |
| `report_evidence_reference_pass` | `true` |
| `hallucinated_citation_count` | `0` |
| `high_risk_false_negative_count` | `0` |
| `report_safety_violation_count` | `0` |
| `diagnosis_or_prescription_violation_count` | `0` |
| `trace_schema_pass` | `true` |
| `all_json_artifacts_valid` | `true` |
| `python -m unittest discover -s tests` | pass |
| `python -m compileall -q app scripts tests` | pass |

## Regression Coverage

The aggregate gate runs:

- P6A knowledge pipeline validation;
- P6B runtime RAG validation;
- JSON artifact validation;
- compileall;
- P4 gate;
- unittest discovery;
- deterministic P5 runtime regression.

The P6B gate disables the real LLM probe inside its embedded P5 regression to keep the gate deterministic. Run `python scripts/run_p5_real_runtime_validation.py` separately in a reachable provider environment to measure real LLM availability.

## Unit Tests

P6B adds:

- `tests/test_p6b_runtime_rag_loader.py`
- `tests/test_p6b_rag_boundary.py`
- `tests/test_p6b_evidence_schema.py`
- `tests/test_p6b_trace.py`
- `tests/test_p6b_gate.py`

These tests cover reviewed-source loading, bad artifact fail-closed behavior, evidence reference metadata, core-state boundary enforcement, trace schema exactness, and light-mode gate metrics.

The API contract gate also checks that public report responses do not expose internal P6B evidence packs, trace payloads, or raw retrieved chunk content. Public payloads retain evidence references for auditability.

## Safety Boundary

The report safety statement is retained: the system is only for consultation information organization and risk reminders. It is not a diagnosis or treatment recommendation and cannot replace clinician judgment.

P6B specifically guards against:

- unapproved source loading;
- smoke-only source loading;
- hallucinated evidence references;
- report safety violations;
- diagnosis or prescription output;
- high-risk false negatives;
- RAG mutation of core state.

## Known Cautions

- Current P6B retrieval uses only synthetic policy text.
- Runtime retrieval is lexical and deterministic; it is not real embedding search.
- Evidence audit storage is JSONL only.
- Full code-health soft tools may still report pre-existing cautions; hard gates remain the release blocker.

## Completion Criteria

P6B is complete when the runtime validator and aggregate gate are `ok`, all JSON artifacts validate, unittest discovery passes, compileall passes, and the generated documents describe source review, runtime flow, evidence references, boundary checks, failure modes, and next-stage limits.
