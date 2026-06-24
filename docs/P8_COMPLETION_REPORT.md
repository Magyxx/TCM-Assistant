# P8 Completion Report

## Snapshot

- Branch: `p8/realpath-validation`
- Validated commit: `63633ccaedd8ccbca3c05f2d1f67390cfa0d5af2`
- Stage: `P8_INTEGRATED_REALPATH_VALIDATION`
- Integrated artifact: `artifacts/p8_realpath_validation.json`
- Result: `status=ok`, `ready_for_main_merge=true`, `ready_for_p1=true`

P8 keeps TCM-Assistant as a consultation assistance system. It organizes intake facts, structured summaries, risk prompts, evidence references, and offline-care suggestions. It does not make deterministic diagnoses, prescribe treatment, or replace clinician judgment.

## Commit Summary

- P8-M1 MemoryManager:
  - `94dc605` added consultation memory models.
  - `00fd8ce` added safe merge policy for consultation facts.
  - `f6086d0` connected turn output and run state bridging.
  - `d2677e7` added case summary and P8 memory validation.
- P8-M2 Graph facade:
  - `2f0d418` added consultation graph state and runtime boundary.
  - `5c64c45` added fallback workflow nodes.
  - `33ca1a3` connected MemoryManager to workflow state updates.
  - `0c33554` added P8 graph validation artifact.
- P8-M3 Structured extractor adapter:
  - `db671a1` added structured result adapter and registry.
  - `e48dc73` covered structured modes and safe real LLM skip.
  - `944d49e` routed extraction through the structured adapter.
  - `776bb18` added P8 extractor validation artifact.
- P8-M4 BM25 realpath and RAG guard:
  - `85590c7` documented BM25 realpath and evidence policy.
  - `f61ea89` added evidence models, query builder, and guard.
  - `3b5b54d` added BM25 realpath metadata retrieval.
  - `51859ff` added the optional RAG retrieval graph node.
  - `63633cc` added P8 RAG verification artifact.
- P8-M5 Integrated validation:
  - `scripts/verify_p8_realpath.py` now runs compileall, unittest, secret scan, P8-M1 through P8-M4 verifiers, artifact parsing, branch protection checks, skip aggregation, safety gates, and readiness decisions.

## Landed Capabilities

- MemoryManager now separates validated L2 facts, derived L3 summaries, audit events, and disabled L4 experience memory boundaries.
- Graph facade supports a sequential fallback runtime and optional LangGraph runtime behind a stable workflow boundary.
- Structured extractor adapter supports fake, fallback, and real LLM modes with schema guarding before memory writes.
- BM25 realpath retrieval, evidence pack generation, and RAG guard checks are available without allowing evidence to overwrite core consultation facts.

## Safety Boundaries

- LLM output cannot directly write risk authority state.
- High-risk `present` status is sticky and cannot be lowered by later low-authority text.
- RAG evidence cannot overwrite core fields such as chief complaint, duration, risk status, or risk rule ids.
- TurnOutput schema failures block memory writes.
- Report/RAG safety checks reject diagnosis and prescription claims.
- Protected refs remained untouched:
  - `v0.7.0-p7-caution` -> `533cb38`
  - `origin/backup/main-before-p7-device1-20260622-e986065` -> `e986065`
  - `origin/sft-local-pipeline` -> `6134244`
  - `exp/sft-lora-extractor` and `origin/exp/sft-lora-extractor` -> `eefdfec`

## Validation Commands

```powershell
git status --short
git log --oneline --decorate -20
python -m compileall -q app scripts tests
python -m unittest discover -s tests
python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json
python scripts/verify_p8_memory.py --json --output artifacts/p8_memory_validation.json
python scripts/verify_p8_graph.py --json --output artifacts/p8_graph_validation.json
python scripts/verify_p8_extractor.py --json --output artifacts/p8_extractor_validation.json
python scripts/verify_p8_rag.py --json --output artifacts/p8_rag_validation.json
python scripts/verify_p8_realpath.py --json --output artifacts/p8_realpath_validation.json
```

## Validation Results

- `compileall`: passed.
- `unittest discover`: passed, 385 tests, 197.402 seconds, `OK`.
- `secret_scan`: passed, `finding_count=0`.
- `verify_p8_memory`: passed.
- `verify_p8_graph`: passed.
- `verify_p8_extractor`: passed.
- `verify_p8_rag`: passed.
- Artifact file existence and JSON parsing: passed.
- Branch protection checks: passed.
- Safety gates: all passed.

## Skipped Tests

No optional checks were skipped in the latest integrated validation. Optional LangGraph runtime passed, real LLM mode passed, and BM25 realpath retrieval passed.

## Artifacts

- `artifacts/secret_scan_result.json`
- `artifacts/p8_memory_validation.json`
- `artifacts/p8_graph_validation.json`
- `artifacts/p8_extractor_validation.json`
- `artifacts/p8_rag_validation.json`
- `artifacts/p8_realpath_validation.json`

## Not Completed In P8

- P8 does not introduce a FastAPI productization rewrite.
- P8 does not add PostgreSQL, Docker rollout work, MCP integration, or a multi-agent runtime.
- P8 does not implement full hybrid RAG with embeddings and reranking.
- P8 does not merge device2 SFT/LoRA code into the device1 mainline.

## P1 Entry Recommendation

P1 should start from the P8 skeleton, not from zero. The recommended first slice is FastAPI service hardening, SQLite session persistence, internal Tool Registry integration, JSON logs with trace ids, and focused ReportSafety strengthening.

## Merge Recommendation

`p8/realpath-validation` is recommended for main-merge review after the P8-M5 generated changes are committed. Do not merge into `main` without explicit user confirmation.
