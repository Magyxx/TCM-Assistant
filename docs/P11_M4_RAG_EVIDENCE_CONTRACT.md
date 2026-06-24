# P11-M4 RAG Evidence Contract

P11-M4 stabilizes the RAG evidence boundary. It does not add hybrid retrieval,
embedding infrastructure, vector databases, rerankers, external model downloads,
or external medical crawling.

## Evidence Schema

The main realpath contract uses `app.rag.models.EvidencePack` and
`EvidenceChunk`.

Each evidence chunk must expose:

- `chunk_id`
- `source_id`
- `title`
- `content`
- `score`
- `source_type`
- `trust_level`
- `metadata`

The realpath retrieval mode is `bm25`.

## BM25 Realpath

`app.rag.evidence_pack.build_evidence_pack` uses `BM25Retriever` and returns a
guarded `EvidencePack`.

`app.rag.retriever_router.retrieve_evidence_pack` exposes the same realpath under
`RAG_BACKEND=bm25_realpath` and degrades to a skipped pack if retrieval raises.

## RAG Boundary

RAG output may enter:

- report evidence
- retrieved evidence context
- advice context
- citations
- metadata

RAG output must not overwrite:

- `chief_complaint`
- `duration`
- `risk_status`
- `risk_flags_status`
- `risk_rule_ids`
- `triggered_rule_ids`
- authoritative memory facts

The guard is implemented by `app.rag.rag_guard`.

## Failure Behavior

Retrieval failure must not interrupt the basic inquiry workflow. A failed
`bm25_realpath` retrieval returns an empty skipped pack with a clear
`skip_reason`, for example `bm25_realpath_failed:RuntimeError`.

## Verification

Run:

```powershell
python -m compileall -q app scripts tests
python -m unittest discover -s tests
python scripts/verify_p11_rag_evidence_contract.py --json --output artifacts/p11/rag_evidence_contract.json
```

The M4 artifact is `artifacts/p11/rag_evidence_contract.json`.
