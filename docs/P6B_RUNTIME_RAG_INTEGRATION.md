# P6B Runtime RAG Integration

Generated: 2026-06-21

## Scope

P6B connects the reviewed P6A knowledge artifacts to the runtime consultation graph, report evidence metadata, trace samples, API smoke validation, and the P6B gate. The product boundary remains unchanged: TCM-Assistant organizes consultation information and risk reminders only. It does not diagnose, prescribe, create treatment plans, or replace clinician judgment.

## P6A Baseline

P6A already provides the formal knowledge pipeline:

- `app/knowledge/pipeline.py`
- `scripts/run_p6_knowledge_pipeline.py`
- `knowledge/processed/p6_chunks.jsonl`
- `knowledge/indexes/p6_bm25_index.json`
- `knowledge/eval/p6_retrieval_safety_eval.json`
- `artifacts/p6_knowledge_pipeline.json`

The current P6A fixture has one approved synthetic policy source, one skipped P5 smoke-only source, two `kb.chunk.v0` chunks, and a 2/2 retrieval safety evaluation pass. No real medical book text is included.

## Runtime Artifact Flow

`app/rag/p6_index_loader.py` reads:

- `knowledge/indexes/p6_bm25_index.json`
- `knowledge/processed/p6_chunks.jsonl`
- `knowledge/source_manifest.example.json`

The loader fails closed for missing files, invalid JSON/JSONL, empty chunk files, index schema mismatch, chunk schema mismatch, duplicate chunk ids, source-review failures, unapproved source ids, rights mismatch, content hash mismatch, index hash mismatch, and chunk-count mismatch. There is no silent fallback path.

`app/rag/p6_runtime_retriever.py` wraps the loaded index with deterministic lexical scoring. It returns a `P6EvidencePack` plus a P6B trace dictionary. The runtime mode is recorded as `p6b_runtime_bm25`.

## Source Manifest Gate

Only sources that pass the P6A source review can enter runtime RAG. Required conditions include:

- `ingestion_status` is `approved_for_p6` or `indexed`.
- rights status is ingestible.
- allowed use includes P6/index/retrieval use.
- rights, safety, and provenance review flags are all true.
- content path stays inside `knowledge/`.

Smoke-only, pending, quarantined, rejected, or unreviewed sources are not loaded into the runtime index.

## Evidence Schema

`app/rag/evidence_schema.py` defines `P6EvidenceChunk`, `P6EvidenceReference`, and `P6EvidencePack`. Each evidence chunk records:

- `source_id`
- `chunk_id`
- `title`
- `content`
- `score`
- `retrieval_mode`
- `index_version`
- `chunk_hash`
- `source_rights_status`
- `source_safety_status`
- `source_provenance_status`

Evidence packs are explicitly read-only for core state and mark diagnosis, prescription, and treatment-plan generation as disallowed.

## Report Integration

The graph `retrieve_knowledge` node now retrieves P6B evidence when RAG is enabled. The report path attaches P6B evidence through `attach_p6_evidence_to_report()`, adding:

- `retrieved_evidence`
- `p6b_evidence_pack`
- `p6b_evidence_references`
- `p6b_report_evidence_reference_pass`
- `rag_core_state_readonly`
- `rag_forbidden_state_writes`
- `rag_retriever_mode`
- `rag_index_version`

The report references are derived only from returned evidence. Empty evidence creates an empty reference list and does not fabricate citations.

FastAPI public report responses keep evidence references but strip full P6B evidence packs, trace payloads, and raw retrieved chunk content from metadata. Full evidence details remain available in validation artifacts and audit JSONL for offline review.

## RAG Boundary

`app/rag/boundary.py` enforces that RAG does not modify core state:

- `chief_complaint`
- `duration`
- `risk_status`
- `risk_rule_ids`
- `risk_flags_status`
- `risk_flags`
- `symptoms`

High-risk status remains rule-first. RAG cannot downgrade a present high-risk state or convert negated risk into present risk through evidence content.

## Trace Integration

`app/observability/trace.py` defines the P6B trace schema. Every runtime RAG call records:

- `session_id`
- `turn_id`
- `trace_id`
- `rag_runtime_enabled`
- `rag_index_path`
- `rag_index_version`
- `chunk_schema_version`
- `source_manifest_version`
- `retrieved_evidence_count`
- `retrieved_chunk_ids`
- `retrieved_source_ids`
- `retrieval_mode`
- `fallback_used`
- `fallback_reason`
- `rag_boundary_pass`
- `latency_ms`
- `created_at`

Sample traces are written to `artifacts/p6b_runtime_rag_trace_samples.json`.

## API and CLI

P6B validation covers the existing FastAPI service path:

- `GET /health`
- `POST /sessions`
- `POST /sessions/{session_id}/turn`
- `POST /sessions/{session_id}/report`

The main CLI validation entrypoint is:

```bash
python scripts/run_p6b_runtime_rag_validation.py
```

The aggregate gate is:

```bash
python scripts/run_p6b_gate.py
```

## Storage

P6B uses lightweight audit storage instead of expanding the SQLite schema. Evidence audit rows are appended to `artifacts/p6b_rag_evidence_audit.jsonl` with trace id, case id, source id, chunk id, chunk hash, index version, and source review status fields.

## Failure Modes

Expected fail-closed behavior:

- missing or invalid P6A artifacts stop runtime loading;
- schema or hash mismatch stops runtime loading;
- unapproved, unreviewed, or smoke-only sources stop runtime loading;
- unsafe evidence-pack authority fails boundary checks;
- report validation fails if the safety boundary is violated;
- trace schema mismatch fails the P6B runtime validation.

Fallback retrieval is not used in P6B. If a future fallback is introduced, it must set `fallback_used=true` and record a non-empty `fallback_reason`.

## Known Limits

- The current knowledge base is a synthetic internal policy fixture, not a real medical corpus.
- Retrieval is deterministic lexical BM25-style scoring, not real embedding search.
- Evidence is stored in JSON artifacts and JSONL audit files, not a normalized database table.
- Real LLM availability remains environment-dependent and is measured by the P5 validation script.

## Next Phase

Recommended next work is P6C/P7 planning for a rights-cleared source acquisition process, explicit source-review workflow, optional database persistence for evidence metadata, and a retrieval evaluation set that stays safely non-diagnostic.
