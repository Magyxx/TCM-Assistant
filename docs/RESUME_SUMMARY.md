# Resume Summary

## One Sentence
TCM-Assistant is a safety-bounded FastAPI and LangGraph intake assistant with deterministic risk rules, layered memory, hybrid RAG citations, session replay, report export, and local eval gates.

## Tech Stack
Python, FastAPI, Pydantic, LangGraph, SQLite, rank-bm25 with stdlib fallback, lightweight hashed dense retrieval, pytest, Docker.

## Highlights
- Frozen legacy API compatibility with additive P10 session endpoints.
- Offline Hybrid RAG with evidence citations and core-state guard.
- Deterministic safety redteam with zero-tolerance diagnosis and prescription gates.
- Final Eval v2 summarizing API, RAG, safety, secret scan, compile, Docker, and regression status.
- LoRA integration contract that keeps local LoRA limited to ExtractorBackend.

## Quantifiable Metrics
RAG recall@3/5, MRR, citation coverage, faithfulness_simple, high-risk false negatives, prompt injection success, RAG injection success, secret log leak count, API smoke pass, Docker smoke status, pytest pass.

## Interview Talk Track
The system separates extraction, authoritative state, deterministic risk rules, evidence retrieval, report safety, persistence, and eval. This makes later LoRA extraction replaceable without weakening safety or state authority.

## Before And After LoRA
Before LoRA, `fake` and fallback extractors drive the same graph and eval. After LoRA, only ExtractorBackend changes; RunState, risk rules, RAG, FinalReport, API, and eval remain owned by the main system.

