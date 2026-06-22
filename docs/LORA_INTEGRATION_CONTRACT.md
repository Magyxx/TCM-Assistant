# LoRA Integration Contract

## Scope
`local_lora` may only replace `ExtractorBackend`. It must not change LangGraph, Pydantic schemas, MemoryManager, risk rules, RAG, ReportSafety, FinalReport, API behavior, or evaluation gates.

## Input
- `user_input`
- optional RunState summary with non-sensitive structured fields

## Output
- `TurnOutput` JSON
- output must pass `TurnOutput.model_validate`

## Failure
Validation failure must use fallback extraction or a clean error. Invalid LoRA output must not be written into RunState.

## Hard Boundaries
- `local_lora` cannot decide final `risk_status`.
- `local_lora` cannot overwrite `risk_rule_ids`.
- `local_lora` cannot generate diagnosis or prescription content.
- Device2 must not commit model weights, adapters, checkpoints, or base model files to ordinary Git.

## Main-System Ownership
The main system still owns MemoryManager, Risk Rules, RAG, ReportSafety, FinalReport, API, and eval.

## Environment
```text
EXTRACTOR_BACKEND=local_lora
LOCAL_LLM_BASE_URL=http://127.0.0.1:8000/v1
LOCAL_LLM_MODEL=tcm-extractor-lora
LOCAL_LLM_API_KEY=
```

## Smoke Contract
The local LoRA server should expose an OpenAI-compatible chat/completions API or adapter endpoint that accepts the input fields above and returns a parseable `TurnOutput` object. The main system treats parse failures as non-authoritative and falls back safely.

