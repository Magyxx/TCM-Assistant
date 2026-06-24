# P8 BM25 Realpath Plan

## Scope
P8-M4 verifies the existing BM25 retrieval path, wraps retrieved chunks in a small evidence pack, and exposes an optional graph retrieval node. It does not add embeddings, reranking, vector databases, GraphRAG, FastAPI, MCP, or diagnosis/prescription generation.

## Realpath
- Primary source: `app/rag/knowledge_base.txt`.
- Primary implementation: `app.rag.bm25_retriever.BM25Retriever`.
- If `rank_bm25` is installed, the retriever uses `BM25Okapi`.
- If `rank_bm25` is unavailable, the existing lexical fallback remains allowed and must be recorded.

## Evidence Pack
P8 evidence is represented as:
- `EvidenceChunk`: source id, chunk id, score, content, source type, trust/risk metadata.
- `EvidencePack`: query, normalized query, BM25 chunks, top_k, guard status, notes.

Evidence packs are read-only context. They may support report impression, advice, citations, and missing-knowledge notes. They must not become patient facts.

## Graph Integration
The P8 graph adds an optional `rag_retrieve` node after `plan_next_action`. It runs only when RAG is enabled and the graph has enough structured state for a summary/report-ready path. Regular turn smoke tests can disable RAG and do not depend on the knowledge base.

## Non-Goals
- No Hybrid RAG rollout.
- No embedding model.
- No reranker.
- No persistence checkpoint for RAG packs.
- No automatic diagnosis or prescription.
