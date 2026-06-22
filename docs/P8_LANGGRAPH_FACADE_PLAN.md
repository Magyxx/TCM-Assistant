# P8 LangGraph Facade Plan

## Scope
P8-M2 wraps the consultation workflow in a small graph facade without rewriting the existing API, CLI, report generation, or Hybrid RAG paths. The facade is additive and is implemented under `app/graph`.

## Main Path
START
-> `normalize_input`
-> `extract_turn`
-> `validate_turn`
-> `memory_update`
-> `risk_check`
-> `plan_next_action`
-> END

## Runtime Boundary
- `ConsultationGraphState` is a Pydantic model.
- Fallback runtime is always available and runs the node sequence directly.
- Optional LangGraph runtime is used only when `langgraph` is importable and invocation succeeds.
- If LangGraph is unavailable, tests skip only the optional smoke check; fallback tests still run.

## Memory Update
The `memory_update` node calls `MemoryManager.apply_turn()`. That preserves P8-M1 rules:
- TurnOutput must pass Pydantic validation before facts enter L2.
- LLM candidates cannot write risk authority fields.
- Empty candidates cannot overwrite non-empty facts.
- Lower-confidence candidates cannot overwrite higher-confidence facts without explicit correction.
- Audit events are written for validation and merge decisions.

## Risk Check
The `risk_check` node evaluates deterministic risk rules after memory update. It writes risk facts through `MemoryManager.apply_risk_evaluation()`, which uses the same P8-M1 merge policy. High-risk `present` remains sticky, and risk status remains rule-first.

## Compatibility
`run_consultation_graph()` keeps the existing public signature:
`run_consultation_graph(run_state, user_input, use_langgraph=True, extractor_mode=None, rag_enabled=True)`.

The returned value remains a dictionary-shaped graph state containing `run_state`, runtime metadata, extractor metadata, and safety fields. Existing CLI defaults are not changed.

## Non-goals
P8-M2 does not add full FastAPI changes, full Hybrid RAG wiring, FinalReport generation, checkpoint persistence, human approval, MCP server, multi-agent handoff, or real LLM requirements.
