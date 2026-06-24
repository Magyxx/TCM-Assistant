# P8 Structured Extractor Adapter Plan

## Scope
P8-M3 adds a unified extractor adapter around the existing fake, fallback, and OpenAI-compatible extraction paths. It does not train LoRA, use the device2 SFT branch, rewrite FastAPI, add full Hybrid RAG, add multi-agent handoff, or merge to main.

## Goals
- Every mode returns one `ExtractorResult` envelope.
- Every candidate output crosses the `TurnOutput` Pydantic schema boundary.
- Missing real LLM config is a safe skip, not a test failure.
- Graph `extract_turn` calls the unified adapter/registry.
- LLM candidates still cannot write risk authority; risk stays rule-first in the MemoryManager/graph path.

## Modes
- `fake`: deterministic local mode for tests and graph smoke.
- `fallback`: local rule/parser fallback with `fallback_used=true`.
- `real_llm`: OpenAI-compatible path using existing project configuration. Missing key, base URL, model, or dependency returns `skip_reason` and a schema-valid fallback TurnOutput when available.

## Schema Guard
The adapter always calls `TurnOutput.model_validate()` before setting `schema_pass=true`. If parsing or validation fails, `turn_output` is set to null and the graph memory update cannot write L2 facts.

## Graph Integration
`app.graph.nodes.extract_turn_node()` uses `ExtractorAdapter`. Graph state records:
- `extractor_mode`
- `schema_valid`
- `final_schema_pass`
- `fallback_used`
- `skip_reason`
- raw JSON/schema metadata

## Artifact
`scripts/verify_p8_extractor.py` writes `artifacts/p8_extractor_validation.json` with mode-level status, schema guard, graph integration, memory block, and risk authority checks.
