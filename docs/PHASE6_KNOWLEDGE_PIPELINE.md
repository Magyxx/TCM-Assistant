# Phase 6 Knowledge Pipeline

Generated: 2026-06-21

## Scope

P6 adds a formal knowledge-base clean/chunk/index/eval pipeline while keeping the runtime product boundary unchanged.

This phase does not change:

- FastAPI request or response schemas.
- SQLite schema.
- `RunState`, `TurnOutput`, or `FinalReport` semantics.
- Risk-rule logic.
- Runtime RAG behavior.
- Diagnosis, prescription, or treatment-plan boundaries.

No real medical book corpus was ingested. The committed P6 source is a tiny synthetic internal policy fixture only.

## Added Pipeline

The P6 runner is:

```bash
python scripts/run_p6_knowledge_pipeline.py
```

It performs:

1. Source manifest parsing.
2. Rights, safety, provenance, and allowed-use review.
3. Cleaning with raw source hash retention.
4. Chunk generation using `kb.chunk.v0`.
5. Chunk content hashing and provenance metadata.
6. Simple lexical index generation using `kb.index.v0`.
7. Retrieval quality evaluation.
8. Safety and RAG boundary evaluation.

The pipeline indexes only manifest entries with:

- ingestible rights status;
- `ingestion_status` of `approved_for_p6` or `indexed`;
- P6/index/retrieval allowed use;
- explicit rights, safety, and provenance review flags;
- a content path inside the `knowledge/` directory.

Sources in `planned_smoke_only`, `pending_review`, `quarantined`, or `rejected` status are not indexed.

## Outputs

The default run writes:

- `knowledge/processed/p6_chunks.jsonl`
- `knowledge/indexes/p6_bm25_index.json`
- `knowledge/eval/p6_retrieval_safety_eval.json`
- `artifacts/p6_knowledge_pipeline.json`

Current artifact status:

- `status`: `ok`
- approved P6 sources: `1`
- skipped non-P6 smoke sources: `1`
- chunks generated: `2`
- retrieval eval cases passed: `2 / 2`
- safety boundary status: `ok`

## Boundary

P6 keeps RAG advisory and read-only:

- `core_state_readonly`: `true`
- `risk_rule_first`: `true`
- `can_diagnose`: `false`
- `can_prescribe`: `false`
- `can_create_treatment_plan`: `false`

P6 retrieval output must not write:

- `chief_complaint`
- `duration`
- `risk_status`
- `risk_rule_ids`
- `risk_flags_status`
- `risk_flags`

## Validation

Focused validation:

```bash
python -m unittest tests.test_p6_knowledge_pipeline
python scripts/run_p6_knowledge_pipeline.py
python -m json.tool artifacts/p6_knowledge_pipeline.json
python -m json.tool knowledge/indexes/p6_bm25_index.json
python -m json.tool knowledge/eval/p6_retrieval_safety_eval.json
```

Broader regression checks remain:

```bash
python scripts/run_code_health_gate.py
python scripts/run_p4_gate.py
python -m unittest discover -s tests
python -m compileall -q app scripts tests
```

## Completion Criteria

P6 is complete when:

- the manifest parses;
- only reviewed and approved P6 sources are indexed;
- cleaned content preserves provenance and hashes;
- chunks conform to `kb.chunk.v0`;
- index generation completes;
- retrieval quality evaluation passes;
- safety boundary evaluation passes;
- RAG remains read-only and high-risk triage remains rule-first.

`artifacts/p6_knowledge_pipeline.json` records all criteria as passing for the current synthetic fixture.
