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
LOCAL_LLM_TIMEOUT_SECONDS=10
LOCAL_LLM_API_KEY=
```

## Smoke Contract
The local LoRA server should expose an OpenAI-compatible chat/completions API or adapter endpoint that accepts the input fields above and returns a parseable `TurnOutput` object. The main system treats parse failures as non-authoritative and falls back safely.

## P10M3 Device1 Integration
- `local_lora` is implemented as `LocalLoRAExtractorBackend`.
- It sends only `user_input` plus a minimal RunState context to an OpenAI-compatible `/chat/completions` endpoint.
- The prompt requires a single `TurnOutput` JSON object and repeats the non-diagnosis / non-prescription boundary.
- Raw model content must parse as JSON or be recovered by bounded JSON-object extraction, then pass `TurnOutput.model_validate`.
- Invalid JSON, schema mismatch, provider errors, timeout, or connection failure return a rule-fallback `TurnOutput` with observable metadata; failed model output is not written as authoritative RunState.
- Risk authority remains in the main Risk Rules layer; RAG remains read-only for core fields.
