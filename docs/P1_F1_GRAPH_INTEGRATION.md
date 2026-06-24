# P1-F1 BM25 Evidence Pack Graph Integration

P1-F1 wires the P1 EvidencePack contract into the graph and report skeleton path without requiring embeddings, a vector database, a real LLM, or a local LoRA service.

## Behavior

- `app.rag.retriever_router.retrieve_evidence_pack()` supports `RAG_BACKEND=bm25_realpath`.
- The BM25 realpath uses the existing local knowledge retriever and converts results into the P1 `EvidencePack` schema.
- P8 graph metadata records `p1_f1_evidence_pack`, `p1_f1_report_skeleton`, and `p1_f1_rag_core_field_overwrite_blocked`.
- P9/P10 graph exports `p1_evidence_pack` and `p1_report_skeleton`, and the final report metadata includes the same pack.

## Safety

RAG remains read-only for core RunState fields. It can support explanation and report advice, but cannot overwrite chief complaint, duration, risk status, or risk rule ids.

## Artifact

`scripts/verify_p1_f1_graph_integration.py` writes `artifacts/p1_f1_graph_integration_validation.json`.
