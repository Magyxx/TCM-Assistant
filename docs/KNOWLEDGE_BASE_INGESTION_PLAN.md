# Knowledge Base Ingestion Plan

Generated: 2026-06-20

## Summary

This plan prepares the repository structure for P5/P6 knowledge base ingestion without importing a real medical book corpus.

Current scope is structure only:

- Create knowledge directory scaffolding.
- Define a source manifest schema.
- Define a chunk schema.
- Provide a synthetic source manifest example.
- Provide a machine-readable ingestion plan artifact.

This change does not alter APIs, application schemas, SQLite schema, risk rules, runtime RAG behavior, or P4 gates.

## Hard Constraints

- Do not commit real medical book full text.
- Do not ingest data with unclear copyright or licensing status.
- Do not ingest modern textbooks without permission.
- Do not ingest annotated or translated editions without permission.
- Do not ingest publisher PDFs or scanned full texts.
- Do not allow RAG to rewrite core consultation state.
- Do not change API/schema/SQLite/risk rules for this phase.
- Do not affect the P4 gate.
- Do not use knowledge base data for diagnosis or prescription generation.
- Do not store real patient conversations in knowledge base L4.
- L4 may store only knowledge, anonymized failed samples, RAG failure cases, and safety boundary lessons.

## Repository Layout

- `knowledge/raw/`: intake staging area for source manifests and approved micro samples only.
- `knowledge/processed/`: future validated chunks generated from approved sources.
- `knowledge/indexes/`: future generated retrieval indexes.
- `knowledge/eval/`: future retrieval and safety evaluation fixtures.

The directories are intentionally empty except for placeholders. P5 must not add a large real corpus.

## Phase Plan

### P5: Small Smoke-Test Corpus Only

P5 is limited to a very small smoke-test corpus. Preferred inputs are synthetic fixtures. Rights-cleared micro samples may be used only after review.

P5 goals:

- Validate source manifest parsing.
- Validate chunk schema parsing.
- Validate hash/version metadata.
- Validate that RAG boundary checks remain intact.

P5 non-goals:

- No full real medical books.
- No modern textbooks.
- No publisher PDF scans.
- No production retrieval behavior.
- No diagnosis or prescription generation from knowledge data.

### P6: Formal Clean/Chunk/Index/Eval Pipeline

P6 introduces the formal pipeline after review controls are in place:

- Source intake through source manifest.
- Rights and safety review.
- Cleaning with provenance retained.
- Chunking into the chunk schema.
- Hashing and versioning.
- Index generation.
- Retrieval quality evaluation.
- Safety and boundary evaluation.

P6 must keep high-risk triage rule-first and must not allow retrieval output to overwrite core state.

Current implementation status:

- `scripts/run_p6_knowledge_pipeline.py` runs the formal P6 pipeline.
- `app/knowledge/pipeline.py` performs source review, cleaning, chunking, hashing, index generation, and retrieval/safety evaluation.
- `knowledge/raw/synthetic_p6_policy_note.txt` is a tiny synthetic internal fixture, not real medical book text.
- `knowledge/processed/p6_chunks.jsonl`, `knowledge/indexes/p6_bm25_index.json`, and `knowledge/eval/p6_retrieval_safety_eval.json` are generated outputs.
- `artifacts/p6_knowledge_pipeline.json` records the P6 completion artifact.
- Runtime API, SQLite, risk rules, and default RAG behavior are unchanged.

### P8: Expanded Corpus and Safety/RAG Evaluation

P8 may expand the corpus only with rights-cleared sources and stronger evaluation:

- Expanded retrieval quality tests.
- Expanded safety regression tests.
- High-risk triage rule-first regression tests.
- RAG failure case review loops.
- Evidence quality and citation audit.

Expanded corpus work remains blocked for any source with unclear rights, missing review, or unsafe intended use.

## Disallowed Data

The following data must not be ingested:

- `rights_status` unknown.
- Modern textbook without permission.
- Annotated or translated editions without permission.
- Publisher PDF scans.
- Patient records.
- Non-anonymized dialogs.
- Real patient conversations.
- Copyright-status-unclear book text.
- Large real medical book full text.

## Source Manifest Schema

Manifest version: `kb.source_manifest.v0`

Each source entry must include at least:

| Field | Type | Meaning |
| --- | --- | --- |
| `source_id` | string | Stable unique source id. |
| `title` | string | Source title. |
| `author` | string | Author or accountable creator. |
| `edition` | string | Edition, version, or `not_applicable`. |
| `publisher` | string | Publisher, archive, owner, or `internal`. |
| `source_type` | string | Source category, such as `synthetic_smoke_note`, `public_domain_text`, `rights_cleared_text`, `internal_policy_note`, `failure_case`, or `safety_boundary_note`. |
| `rights_status` | string | Rights state, such as `synthetic_owned`, `public_domain_verified`, `permission_granted`, `internal_owned`, or `rejected`. Unknown is not allowed for ingestion. |
| `license` | string | License, rights statement, or permission reference. |
| `allowed_use` | array | Approved uses for ingestion, testing, retrieval, or evaluation. |
| `forbidden_use` | array | Explicitly prohibited uses. |
| `ingestion_status` | string | `planned_smoke_only`, `pending_review`, `approved_for_p6`, `indexed`, `quarantined`, or `rejected`. |
| `trust_level` | string | `fixture_low`, `reviewed_medium`, `reviewed_high`, or `policy_high`. |
| `review_required` | boolean | Whether source review is required before ingestion or use. |

Source entries that fail rights, safety, or provenance review must be marked `rejected` or `quarantined` and must not be indexed.

## Chunk Schema

Chunk version: `kb.chunk.v0`

Each processed chunk must include at least:

| Field | Type | Meaning |
| --- | --- | --- |
| `chunk_id` | string | Stable unique chunk id. |
| `source_id` | string | Source id from the manifest. |
| `source_type` | string | Source type copied from the manifest. |
| `title` | string | Source or document title. |
| `section` | string | Section, chapter, heading, or fixture section. |
| `content` | string | Chunk text. |
| `entities` | array | Extracted entities. |
| `normalized_terms` | array | Normalized terminology. |
| `risk_level` | string | `low`, `medium`, `high`, `emergency`, or `not_applicable`. |
| `trust_level` | string | Source-derived trust level. |
| `rights_status` | string | Source-derived rights status. |
| `version` | string | Chunk schema/content version. |
| `hash` | string | Content hash for traceability. |

P5 chunks must be synthetic or rights-cleared micro samples only. Chunks must not include patient identifiers or non-anonymized patient dialogs.

## RAG Boundary

RAG may support:

- Impression.
- Advice.
- Report explanation.
- Evidence snippets.

RAG must not modify:

- `chief_complaint`
- `duration`
- `risk_status`
- `risk_rule_ids`

High-risk triage remains rule-first. RAG must not diagnose, prescribe, create treatment plans, downgrade high risk, or rewrite core consultation state.

## L4 Storage Boundary

L4 knowledge storage may include:

- Knowledge.
- Anonymized failed samples.
- RAG failure cases.
- Safety boundary lessons.

L4 must not include:

- Real patient conversations.
- Non-anonymized dialogs.
- Patient records.
- Material derived from unclear rights.

## Review Workflow

1. Register source metadata in `knowledge/source_manifest.example.json` format.
2. Review rights, license, provenance, and allowed use.
3. Reject or quarantine any source with unclear rights.
4. For P5, create only synthetic or rights-cleared micro samples.
5. Validate chunks against `kb.chunk.v0`.
6. Compute hashes and preserve source metadata.
7. Run retrieval and safety boundary tests before any runtime use.
8. Keep RAG evidence advisory and keep risk triage rule-first.

## Validation

Run these checks after scaffold changes:

```bash
python scripts/run_code_health_gate.py
python scripts/run_p4_gate.py
python -m unittest discover -s tests
python -m compileall -q app scripts tests
python -m json.tool artifacts/kb_ingestion_plan.json
```
