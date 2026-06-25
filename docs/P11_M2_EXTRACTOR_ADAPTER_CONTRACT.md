# P11-M2 Extractor Adapter Contract

P11-M2 hardens the extractor boundary established in P11-M1. Every extractor
backend is treated as a candidate producer, not as an authoritative state writer.

## Backend Protocol

Backends implement `ExtractorBackend`:

- `extract(user_input, state=None, memory=None, config=None, session_id=None, turn_id=None) -> ExtractorResult`
- `extract_turn(user_input, state=None) -> TurnOutput`

The supported mainline backend names are:

- `fake`
- `fallback`
- `rule_fallback`
- `real_llm`
- `openai_compatible`
- `cloud_llm`
- `local_vllm`
- `local_lora`

`fallback` is a route alias for the `rule_fallback` backend. `cloud_llm` is an
alias for the OpenAI-compatible backend shape.

## Result Contract

Every backend result must be readable through `ExtractorResult.contract_summary()`.
The stable fields are:

- `backend_name`
- `backend_mode`
- `status`
- `schema_pass`
- `candidate_schema_pass`
- `schema_guard`
- `validated_output_schema_guard`
- `fallback_used`
- `latency_ms`
- `error_type`
- `skip_reason`
- `json_valid`
- `raw_llm_json_valid`
- `repair_used`
- `repair_supported`
- `retry_count`
- `retry_supported`

`schema_pass` describes whether the returned `TurnOutput` object is usable after
the adapter boundary. `candidate_schema_pass` records whether the original LLM
candidate passed its own schema guard before any safe fallback was returned.

## Schema Guard

All backend output must enter the `TurnOutput` schema guard before any
authoritative workflow state write. Invalid candidates may be retained as raw
evidence only. They must not update `RunState` directly.

When a candidate fails but a safe rule fallback is returned:

- `schema_guard=failed`
- `validated_output_schema_guard=passed`
- `candidate_schema_pass=false`
- `fallback_used=true`

## Malformed JSON And Repair

Malformed JSON from `real_llm`, `local_vllm`, or `local_lora` must be recorded
explicitly. It cannot be silently swallowed.

Required metadata:

- `raw_llm_json_valid=false`
- `json_valid=false` when no JSON object can be parsed
- `error_type=json_invalid` or a more specific schema/parser error
- `repair_used=true` when lightweight JSON unwrap succeeds
- `retry_count=0` when retry is unsupported or not attempted

P11-M2 does not introduce a complex retry engine.

## Fallback And Optional Backend Skips

Any safe rule fallback must set `fallback_used=true`.

Optional live backends must expose a skip reason when unavailable:

- `real_llm`, `openai_compatible`, `cloud_llm`: disabled or missing `OPENAI_*`
  configuration
- `local_vllm`, `local_lora`: live smoke skipped unless
  `RUN_LOCAL_VLLM_SMOKE=1`

`local_vllm` and `local_lora` are never default hard dependencies.

## Risk Authority

Extractor risk fields are candidate observations. Final risk authority remains
with the auditable risk rules layer. `local_lora` and `local_vllm` cannot clear,
downgrade, or directly decide final risk status.

## Verification

Run:

```powershell
python -m compileall -q app scripts tests
python -m unittest discover -s tests
python scripts/verify_p11_post_lora_contract.py --json --output artifacts/p11/post_lora_runtime_contract.json
python scripts/verify_p11_extractor_adapter.py --json --output artifacts/p11/extractor_adapter_contract.json
```

The M2 artifact is `artifacts/p11/extractor_adapter_contract.json`.
