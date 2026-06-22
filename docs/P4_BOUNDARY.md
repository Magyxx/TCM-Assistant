# P4 Boundary: Safety, API, Schema, RAG, Memory, Tooling

## Medical Safety Boundary

The system is for consultation information organization and risk prompting only.

It may organize consultation information, identify risk signals, summarize the consultation, and advise offline medical care when high-risk signals are present.

It must maintain:

- No diagnosis.
- No prescription.
- No treatment plan.
- No doctor replacement.
- High-risk signals should advise offline medical care.
- Report should remain cautious and explanatory.

P4 must not convert workflow, RAG, memory, tools, or LLM output into medical decision automation.

## Risk Boundary

- Rules are authoritative for high-risk.
- LLM cannot override `risk_status`.
- RAG cannot override `risk_status`.
- `risk_rule_ids` cannot be edited by LLM/RAG.
- Present high-risk cannot be silently downgraded.
- Negation handling must be explicit.
- Risk reasons and user evidence should remain auditable.
- High-risk rule matches must remain visible in state or report audit metadata where applicable.

If model output, RAG evidence, memory, or a tool conflicts with deterministic high-risk rules, the deterministic rule result wins.

## API Boundary

- P4.0 no API changes.
- P4.1+ must preserve public API contract.
- Response body schema frozen unless a future migration explicitly gates it.
- Existing clients must continue to work.
- Additive optional fields require compatibility review.
- Existing endpoint paths and methods remain compatible.
- Error shape remains compatible with the current `error.code`, `error.message`, and `error.details` structure.

No P4.0 document or artifact authorizes an API contract change.

## SQLite / Persistence Boundary

- P4.0 no SQLite schema change.
- P4.1 no SQLite schema change.
- P4.2+ schema changes require migration plan, rollback, and historical session compatibility.
- Existing sessions must remain readable.
- Existing `schema_version=1` compatibility remains the baseline.
- Existing tables `schema_meta`, `sessions`, `session_states`, `turns`, and `reports` remain the compatibility contract.
- No ORM migration is introduced in P4.0.

Any future persistence change must include explicit migration and rollback evidence before release.

## Pydantic Schema Boundary

- Current schemas remain authoritative.
- LLM output must validate before state write.
- No raw LLM JSON directly enters authoritative state.
- Schema failures must use retry/fallback, not silent acceptance.
- `RunState` remains the authoritative structured consultation state until a future migration explicitly gates an equivalent contract.
- `TurnOutput` remains candidate extraction output.
- `FinalReport` remains the report output schema.

P4.0 does not change Pydantic runtime models.

## RAG Boundary

RAG can:

- enhance impression
- enhance advice
- enhance report explanation
- provide evidence snippets

RAG cannot:

- rewrite `chief_complaint`
- rewrite `duration`
- rewrite `risk_status`
- rewrite `risk_rule_ids`
- downgrade high-risk
- invent user symptoms
- produce diagnosis/prescription
- produce treatment plans

RAG is read-only with respect to core consultation state. High-risk judgment remains rule-first.

## Memory Boundary

- Memory is consultation safety memory, not user profile.
- L1 recent turns are context only.
- L2 structured state is authoritative.
- L3 summary cannot overwrite L2.
- L4 stores knowledge or anonymized evaluation experience only.
- No raw patient PII in vector memory.
- Every key report field should have a source where possible.
- Memory cannot silently downgrade high-risk signals.
- Memory cannot turn a consultation assistant into a longitudinal patient profile system.

P4.0 does not implement MemoryManager.

## Tool Boundary

- Internal Tool Registry before MCP.
- Tool permission levels required.
- Side effects must be declared.
- Human approval required for risky or destructive tools.
- Audit log required.
- Tools cannot bypass risk/report safety boundaries.
- Tools cannot write authoritative state unless their outputs pass schema validation and permission checks.
- Tools cannot produce diagnosis, prescription, treatment plans, or doctor-replacement claims.

P4.0 does not implement Tool Registry runtime code.

## Explicit Non-Goals For P4.0

- LangGraph implementation
- MemoryManager implementation
- Embeddings
- Tool Registry runtime
- Web UI
- User/auth system
- ORM
- MCP Server
- Multi-agent
- GraphRAG
- API contract change
- Response body schema change
- SQLite schema change
- Diagnosis
- Prescription
- Treatment recommendation

P4.0 only records boundaries and migration design.
