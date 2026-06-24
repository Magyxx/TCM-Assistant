# P11 Backend Matrix

This matrix describes the P11-M1 mainline extractor contract. Runtime source of
truth is `app.extractors.router.get_backend_contract_matrix()`.

| Backend | Default | Required Env | Live Service | CI Safe | Skip Reason |
| --- | --- | --- | --- | --- | --- |
| `fake` | yes | none | no | yes | none |
| `fallback` / `rule_fallback` | no | none | no | yes | none |
| `real_llm` | no | `ENABLE_REAL_LLM`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` | yes | skipped by default | `ENABLE_REAL_LLM=false` or `missing_api_config:...` |
| `openai_compatible` / `cloud_llm` | no | `ENABLE_REAL_LLM`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` | yes | skipped by default | `ENABLE_REAL_LLM=false` or `missing_api_config:...` |
| `local_vllm` | no | `LOCAL_LLM_BASE_URL`, `LOCAL_LLM_MODEL` | yes | static/mock only | `RUN_LOCAL_VLLM_SMOKE is not enabled` for live smoke |
| `local_lora` | no | `LOCAL_LLM_BASE_URL`, `LOCAL_LLM_MODEL` | yes | static/mock only | `RUN_LOCAL_VLLM_SMOKE is not enabled` for live smoke |
| `local_base` | no | none | no | yes | `reserved_for_device2_integration` |

## Common Output Contract

All active backends return `ExtractorResult`. Successful candidates must validate
as `TurnOutput`. Failed candidates record schema/json metadata and must not write
authoritative state.

## Backend Notes

### fake

`fake` is deterministic and remains the default safe backend for local and CI gates.
It does not require API keys, GPU, vLLM, or model files.

### fallback / rule_fallback

The rule fallback path is deterministic and always testable. It records
`fallback_used=true` and keeps high-risk rule output auditable.

### real_llm / openai_compatible / cloud_llm

Cloud-compatible backends are optional. They are skipped by default unless explicitly
enabled and configured. Missing keys or disabled real LLM settings are expected skip
conditions, not P11-M1 failures.

### local_vllm

`local_vllm` is registered but not a default dependency. Interface and fallback
behavior are covered by static/mock tests. Live service smoke is out of scope unless
`RUN_LOCAL_VLLM_SMOKE=1`.

### local_lora

`local_lora` is registered as a TurnOutput candidate extractor. It may not become
the default backend and may not decide final risk authority. Malformed JSON and
schema-mismatched candidates are rejected and routed to auditable fallback metadata.

## Test Coverage

P11-M1 adds regression coverage for:

- backend registration and default behavior
- optional backend skip reasons
- local LoRA malformed JSON/schema guard
- local LoRA inability to bypass risk rules
- absence of old `extract_turn(state, user_input)` dependency
- absence of `BackendResult` in tests
- RAG core field overwrite guard
