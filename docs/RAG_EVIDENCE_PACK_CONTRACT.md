# RAG EvidencePack Contract

P1-F0 uses a small BM25 stub contract. It does not require embeddings, pgvector, Qdrant, Milvus, or recall metric acceptance.

## EvidenceChunk

- `chunk_id`
- `source_id`
- `title`
- `content`
- `score`
- `source_type`
- `trust_level`
- `metadata`

## EvidencePack

- `query`
- `backend`
- `chunks`
- `skipped`
- `skip_reason`
- `created_at`

RAG may strengthen explanations and advice. It must not overwrite `chief_complaint`, `duration`, `risk_status`, or `risk_rule_ids`.

## P1-F1 BM25 Realpath

`RAG_BACKEND=bm25_realpath` converts the existing local BM25 retriever output into this P1 contract. If the realpath cannot run, the pack is marked `skipped` with a `skip_reason`; it does not require embedding or vectorstore services.

## P1-F2 API Exposure

The same contract is exposed as `p1_evidence_pack` on the main API and `evidence_pack` on the P1 wrapper. Exposure is read-only and does not grant RAG authority over core state fields.
