# P10M2 RAG Design

## Knowledge Scope
The knowledge repository contains only inquiry guidance, red flags, terminology synonyms, and safety boundaries. It excludes diagnosis conclusions, prescriptions, and unverified treatment advice.

## Chunk Schema
Each chunk has `chunk_id`, `source_id`, `source_type`, `title`, `content`, `entities`, `risk_level`, `trust_level`, and `version`.

## Retrieval
P10M2 uses offline hybrid retrieval:
- BM25 lexical retrieval with stdlib fallback.
- Lightweight hashed dense fallback with no model download.
- Weighted fusion plus simplified RRF.
- Per-result `bm25_score`, `dense_score`, `fusion_score`, and `citation_id`.

## Guard
RAG output may write evidence, citations, and metadata only. It cannot write `chief_complaint`, `duration`, `risk_status`, `risk_rule_ids`, `risk_reasons`, or user-stated negations.

## Citation
RAG-enhanced report content must be traceable to `evidence_ids` and `evidence_citations`. If no RAG evidence is used, citation coverage is `not_applicable`.

