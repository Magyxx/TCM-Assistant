# P4.3 RAG Boundary Report

Generated: 2026-06-20

## Summary

P4.3 adds a bounded RAG evidence boundary.

Implemented:

- `app/rag/evidence_boundary.py`
- `EvidencePack`
- `build_evidence_pack`
- core state snapshot checks
- report metadata attachment for evidence packs
- graph integration for `rag_evidence_pack`
- `tests/test_p4_3_rag_boundary.py`
- `artifacts/p4_3_rag_boundary.json`

## Boundary

RAG can support report explanation, impression, advice, and evidence snippets.

RAG cannot rewrite:

- `chief_complaint`
- `duration`
- `risk_status`
- `risk_rule_ids`
- `risk_flags_status`
- `risk_flags`

RAG cannot diagnose, prescribe, create treatment plans, or downgrade high risk.

## Rollback

Rollback path: stop attaching P4 evidence packs and use the existing RAG metadata or no RAG.

