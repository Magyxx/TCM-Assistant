# P6C Source Governance Design

Generated: 2026-06-22

## Baseline

P5 real runtime validation, P6A knowledge pipeline governance, and P6B runtime RAG integration are complete. P6C builds on those phases without changing the product boundary: TCM-Assistant organizes consultation information and risk reminders only. It does not diagnose, prescribe, create treatment plans, or replace clinician judgment.

## Goal

P6C upgrades the synthetic P6 knowledge fixture into an auditable source governance system. It does not introduce real medical book text. The current runtime corpus remains an internal synthetic policy fixture with explicit rights, safety, provenance, and permission metadata.

## Source Registry

The registry lives at `knowledge/sources/source_registry.json`, with schema notes in `knowledge/sources/source_manifest.schema.json`. Each source declares:

- identity: `source_id`, `title`, `source_type`, `language`, `version`, `hash`
- review state: `rights_status`, `safety_status`, `provenance_status`, `reviewer`, `reviewed_at`
- permissions: `approved_for_runtime`, `approved_for_eval`, `approved_for_training`, `approved_for_public_demo`
- safety flags: `contains_medical_claims`, `contains_prescription_content`, `contains_diagnosis_content`, `contains_pii`

Runtime permission is independent from training and public-demo permission. A runtime-approved source is not automatically training-approved.

## Review Workflow

`app/knowledge/source_review.py` checks:

- rights review
- safety review
- provenance review
- runtime permission review
- training permission review
- public demo permission review
- prescription content review
- diagnosis content review
- PII review
- staleness review
- hash integrity review

The CLI entrypoints are:

```bash
python scripts/run_p6c_source_review.py
python scripts/run_p6c_source_registry_validation.py
```

Artifacts are written to `artifacts/p6c_source_review.json` and `artifacts/p6c_source_registry_validation.json`.

## Runtime Gate

Runtime indexing is fail-closed. A source cannot enter runtime RAG unless rights, safety, and provenance are all approved; `approved_for_runtime=true`; PII is absent; prescription content is absent unless the source is explicitly a safety negative sample; and the source hash matches the referenced content.

Smoke-only, unknown-rights, unknown-provenance, rejected, quarantined, or failed-safety sources are excluded from runtime.

## Pipeline Integration

`app/knowledge/pipeline.py` now defaults to the P6C source registry while still accepting the legacy P6 manifest through `--manifest`. The pipeline continues to write:

- `knowledge/processed/p6_chunks.jsonl`
- `knowledge/indexes/p6_bm25_index.json`
- `knowledge/eval/p6_retrieval_safety_eval.json`
- `artifacts/p6_knowledge_pipeline.json`

Each chunk now carries `source_hash`, `registry_version`, `review_version`, and `source_registry_metadata`. The index records a `source_review_fingerprint` and exposes a stale-index warning hook if review state changes.

## Retrieval Eval

P6C expands retrieval evaluation with `knowledge/eval/p6c_retrieval_eval_cases.jsonl`. It covers colloquial symptoms, fixed risk terms, TCM terms, negated risk, report enhancement, diagnosis requests, prescription requests, and RAG injection wording.

The runner is:

```bash
python scripts/run_p6c_retrieval_eval.py
```

Outputs:

- `artifacts/p6c_retrieval_eval.json`
- `knowledge/eval/p6c_retrieval_safety_eval.json`

## RAG Injection Defense

RAG evidence remains read-only. Malicious retrieved text cannot change `chief_complaint`, `duration`, `risk_status`, `risk_rule_ids`, `risk_flags_status`, `risk_flags`, or symptoms. RAG cannot diagnose, prescribe, create treatment plans, downgrade high-risk triage, or override rule-first risk logic.

## Evidence Metadata Audit

`app/rag/evidence_audit.py` records evidence metadata for runtime and eval retrieval. Audit rows include trace id, session id, query id, source id, chunk id, chunk hash, source hash, index version, registry version, review version, retrieval mode, score, source review statuses, runtime approval, report usage section, and `core_state_mutated`.

The audit JSONL is `artifacts/p6c_evidence_metadata_audit.jsonl`.

## Failure Modes

P6C fails closed for missing registry files, invalid JSON, schema mismatch, source hash mismatch, chunk hash mismatch, unknown rights, unknown provenance, failed safety review, PII sources, smoke-only runtime loading, unapproved source loading, RAG boundary violations, hallucinated citations, diagnosis/prescription violations, and invalid audit records.

## Gate

`scripts/run_p6c_gate.py` aggregates source registry validation, source review, P6 pipeline, P6B runtime RAG validation, P6C retrieval eval, evidence audit validation, P5 regression, unittest, compileall, P4 gate, and JSON artifact validation.

## Known Limits

- The corpus remains synthetic/internal policy text, not a rights-cleared medical book corpus.
- Retrieval remains deterministic lexical scoring, not real embedding search.
- Evidence audit storage is JSONL, not normalized database persistence.
- Source review is file-based and deterministic; it is not yet an operator UI/workflow.

## P7 Recommendation

P7 should add a real rights-cleared acquisition workflow, reviewer sign-off records, optional evidence metadata database persistence, larger retrieval-eval sets, and a release process for adding or removing runtime sources.
