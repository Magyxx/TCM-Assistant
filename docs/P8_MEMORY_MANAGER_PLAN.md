# P8 MemoryManager Plan

## Scope
P8-M1 adds an engineering memory layer for the consultation workflow. It does not add diagnosis, prescription, FastAPI rewrites, full Hybrid RAG rewrites, MCP servers, or long-term patient history storage.

## Memory Layers
- L1 `recent_turns`: bounded recent turn previews for active-session context.
- L2 `facts`: authoritative structured facts, keyed by RunState-compatible field names.
- L3 `case_summary`: generated from L2 facts only; it is never used to overwrite L2.
- L4 `l4_experience`: disabled storage interface for knowledge or anonymized experience only.

## P8 Components
- `app/memory/models.py`: Pydantic models for facts, audit events, recent turns, summaries, and the consultation memory envelope.
- `app/memory/merge_policy.py`: deterministic write policy for candidate facts.
- `app/memory/audit.py`: audit event construction.
- `app/memory/summary.py`: P8 case summary generation while preserving P7 summary helpers.
- `app/memory/manager.py`: P7-compatible snapshot methods plus P8 `apply_turn()` and `export_run_state()`.

## Apply Turn Flow
1. Append a redacted L1 recent-turn preview.
2. Validate candidate output through `TurnOutput.model_validate()`.
3. Reject invalid schema output before it reaches L2.
4. Convert validated TurnOutput fields into candidate facts.
5. Convert deterministic risk-rule evaluation into risk candidate facts when supplied.
6. Apply merge policy field by field.
7. Write every accepted or rejected update to `audit_events`.
8. Regenerate L3 case summary from L2 facts.

## RunState Bridge
`MemoryManager.export_run_state()` converts L2 facts back into a RunState-compatible object. The exported RunState includes the P8 memory snapshot in metadata so older graph/report paths can continue to consume RunState while P8 keeps fact traceability.

## Acceptance
P8-M1 is accepted when:
- valid TurnOutput updates L2 facts with trace metadata,
- invalid TurnOutput is rejected with audit evidence,
- risk status remains rule-first,
- high-risk `present` cannot be silently downgraded,
- RAG evidence cannot overwrite core fields,
- L3 summary is generated from L2 only,
- L4 stores no raw patient text or identifiers,
- `artifacts/p8_memory_validation.json` is generated.
