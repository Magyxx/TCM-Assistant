# P8 To P1 Handoff

## Position

P1 should continue from the P8 skeleton. It should not restart the project from zero, and it should not bypass P8 safety boundaries.

The P8 baseline gives P1 these anchors:

- MemoryManager for validated facts, summaries, risk authority protection, and audit events.
- Graph facade for fallback workflow execution and optional LangGraph runtime.
- Structured extractor adapter for fake, fallback, and real LLM modes.
- BM25 realpath retrieval, evidence packs, and RAG guard boundaries.
- Integrated validation through `scripts/verify_p8_realpath.py`.

## Recommended P1 Order

1. FastAPI service hardening
   - Keep the existing consultation assistance boundary.
   - Expose P8 workflow behavior through stable service routes.
   - Preserve schema validation before state mutation.

2. SQLite session persistence first, PostgreSQL later
   - Start with SQLite for local productization and regression tests.
   - Keep PostgreSQL as a later deployment option after the session contract is stable.
   - Persist enough metadata for traceability, not raw unbounded private text.

3. Internal Tool Registry
   - Keep tool access explicit and permissioned.
   - Treat tools as bounded helpers, not autonomous diagnosis agents.
   - Record tool calls in audit logs where relevant.

4. JSON logs and trace ids
   - Add consistent `trace_id`, `session_id`, and `turn_id` propagation.
   - Keep logs redacted by default.
   - Make validation artifacts and runtime logs easy to correlate.

5. Hybrid RAG, embedding, and reranker
   - Build on the P8 BM25 realpath and evidence pack.
   - Introduce embeddings and reranking incrementally.
   - Keep RAG evidence unable to overwrite core consultation facts or risk authority fields.

6. ReportSafety strengthening
   - Continue blocking deterministic diagnosis claims.
   - Continue blocking prescription claims.
   - Prefer offline medical evaluation prompts for high-risk signals.
   - Preserve clinician-judgment disclaimers without turning them into diagnosis output.

7. Docker
   - Add containerization only after the P1 service and persistence contracts are stable.
   - Keep environment variables and secrets out of committed artifacts.

8. PII redaction and audit strategy
   - Redact secrets and identifiers from logs, artifacts, and error paths.
   - Keep audit events structured and minimal.
   - Do not store raw patient text in experience memory.

## Explicit Non-Goals

- Do not build a multi-agent product runtime in P1.
- Do not add automatic diagnosis.
- Do not add automatic prescription.
- Do not let LLM output override risk authority state.
- Do not let RAG evidence overwrite core consultation facts.
- Do not merge device2 SFT/LoRA code into the device1 mainline.

## Device2 LoRA Boundary

Device2 LoRA work may be considered only as a future extractor plugin candidate. It must remain behind the structured extractor adapter and schema guard. It must not directly control risk authority state, MemoryManager facts, report safety decisions, or merge readiness.

## First P1 Slice

Start with:

- FastAPI service surface for the P8 workflow.
- SQLite session persistence.
- Internal Tool Registry wiring.
- JSON logs with `trace_id`.

This slice is small enough to validate without weakening the P8 safety gates.
