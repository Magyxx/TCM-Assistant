# P11 Runtime Contract

## Extractor Backend Input

Every extractor backend is called through the router with:

- `user_input`: current turn text
- `state`: optional `RunState` context
- `memory`: optional memory snapshot
- optional `config`, `session_id`, and `turn_id`

Backends must not mutate `RunState` directly. They return an `ExtractorResult`.

## Extractor Backend Output

The only accepted candidate payload is a `TurnOutput` or a structure that can be
validated into `TurnOutput`.

The returned `ExtractorResult` records:

- `mode`
- `turn_output`
- `schema_pass`
- `fallback_used`
- `skip_reason`
- `latency_ms`
- `metadata.backend`
- `metadata.raw_llm_json_valid`
- `metadata.final_schema_pass`
- `metadata.schema_guard`

## Schema Guard Position

The schema guard sits before authoritative state writes:

1. backend returns a candidate
2. candidate is validated as `TurnOutput`
3. graph validation confirms schema status
4. memory/state update may use validated candidate fields
5. risk rules run as the final risk authority

If candidate validation fails, `turn_output` is absent or replaced by an auditable
safe fallback. Invalid candidates must not write authoritative `RunState`.

## Malformed JSON

Malformed JSON from `real_llm`, `local_vllm`, or `local_lora` is not fatal to the
mainline. The backend records:

- `raw_llm_json_valid=false`
- `schema_guard=failed`
- `error_type=json_invalid` or another specific parser/schema error
- `fallback_used=true` when a safe rule fallback is returned

The malformed payload itself remains raw evidence only. It is not trusted state.

## Fallback Recording

Any rule fallback path must set `fallback_used=true`. If the backend was optional
or live-service dependent, the result also has a `skip_reason`.

Examples:

- `real_llm`: `ENABLE_REAL_LLM=false` or `missing_api_config:...`
- `local_lora`: `RUN_LOCAL_VLLM_SMOKE is not enabled` for live smoke, or
  `service_not_available:<error_type>` for an explicitly selected unavailable local service
- `local_vllm`: same local-service rule as `local_lora`

## Risk Authority

Extractor risk fields are candidate observations only. The final risk status comes
from the main risk rules layer or another auditable rule layer.

`local_lora` and `local_vllm` must not clear or downgrade:

- `risk_flags_status`
- `risk_flags`
- `risk_reasons`
- `triggered_rule_ids`

If user input contains chest pain, breathing difficulty, persistent high fever,
GI bleeding, severe abdominal pain, or consciousness changes, the risk rules
fallback must still promote the final state.

## RAG Boundary

RAG evidence may enter report/evidence fields. It may not overwrite:

- `chief_complaint`
- `duration`
- `risk_status` / `risk_flags_status`
- `risk_rule_ids` / `triggered_rule_ids`
- memory L2 facts

The guard is implemented by `app.rag.rag_guard`.

## Optional Backend Skip Reasons

Optional backends must not silently pass or silently fail when not configured.

| Backend | Skip Reason Rule |
| --- | --- |
| `real_llm` / `openai_compatible` / `cloud_llm` | disabled by `ENABLE_REAL_LLM=false` or missing `OPENAI_*` config |
| `local_vllm` | live smoke skipped unless `RUN_LOCAL_VLLM_SMOKE=1` |
| `local_lora` | live smoke skipped unless `RUN_LOCAL_VLLM_SMOKE=1` |
| `local_base` | reserved backend skips as `reserved_for_device2_integration` |

Live vLLM smoke is optional and must only run when the environment explicitly sets
`RUN_LOCAL_VLLM_SMOKE=1`.
