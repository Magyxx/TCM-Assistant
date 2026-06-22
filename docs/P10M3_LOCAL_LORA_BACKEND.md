# P10M3 Local LoRA Backend

P10M3 connects `local_lora` as a Device1 `ExtractorBackend` only. It does not train LoRA, download base models, require CUDA, require vLLM, or commit model weights, adapters, checkpoints, or private data.

## Runtime Boundary

`LocalLoRAExtractorBackend` accepts:
- `user_input`
- optional RunState context with non-sensitive structured fields

It returns:
- `TurnOutput` JSON after `TurnOutput.model_validate`

The backend is selected with:

```text
EXTRACTOR_BACKEND=local_lora
LOCAL_LLM_BASE_URL=http://127.0.0.1:8000/v1
LOCAL_LLM_MODEL=tcm-extractor-lora
LOCAL_LLM_TIMEOUT_SECONDS=10
```

The local endpoint must expose an OpenAI-compatible `/chat/completions` API. Device1 sends a JSON-object response format hint, but still validates the returned content itself.

## Safety Ownership

`local_lora` is a single-turn structured extraction candidate. It must not diagnose, prescribe, or decide final risk. Its `risk_flags` and `risk_flags_status` are not authoritative. The graph merges only non-risk fields before running deterministic Risk Rules, and high-risk stickiness remains owned by the main system.

RAG evidence remains read-only for core fields and cannot overwrite `chief_complaint`, `duration`, `risk_status`, `risk_rule_ids`, `risk_reasons`, or negation fields.

## Failure Behavior

Invalid JSON, schema mismatch, connection failure, timeout, provider JSON errors, and missing message content all fall back to the rule extractor. The returned `TurnOutput.metadata` records:
- `backend=local_lora`
- `fallback_used`
- `error_type`
- `error_message_preview`
- `json_valid`
- `raw_llm_json_valid`
- `schema_valid`
- `final_schema_pass`
- `repair_used`

Live smoke marks an unreachable local server as `skipped`, not failed. Mock tests cover the backend without vLLM or model weights.

## Device Split

Device1 owns API routing, schema validation, fallback, mock/live smoke, backend comparison scaffolding, and safety regressions.

Device2 owns model serving, adapter files, checkpoints, base model access, and any real LoRA training or inference infrastructure.
