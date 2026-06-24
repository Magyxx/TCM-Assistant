# P10-M4A Extractor Contract Reconciliation

P10-M4A reconciles the existing extractor paths behind one auditable backend
contract. It does not replace the graph, merge device2 training work, or add
model weights to Git.

## Contract

Each `ExtractorBackend` accepts a user turn plus optional state, memory, config,
session id, and turn id. The canonical runtime method is:

```python
backend.extract(user_input, state=run_state, memory=memory)
```

It returns `ExtractorResult` with:

- `raw_output`
- `parsed_output` / `parsed_json`
- `turn_output`
- `schema_pass`
- `raw_json_valid`
- `fallback_used`
- `backend`
- `model`
- `latency_ms`
- `error`
- `skip_reason`

The legacy `extract_turn()` method remains available for older callers and
returns the validated or fallback `TurnOutput`.

## Supported Backends

- `fake`: deterministic local contract path for tests and gates.
- `fallback` / `rule_fallback`: rule fallback path, explicitly marked with
  `fallback_used=true`.
- `real_llm` / `openai_compatible` / `cloud_llm`: OpenAI-compatible cloud path.
  If real LLM execution is disabled or configuration is missing, it returns a
  schema-valid rule fallback with a clear `skip_reason`.
- `local_lora`: local OpenAI-compatible LoRA service. If the service is not
  reachable, it returns a rule fallback and records
  `skip_reason=service_not_available:*`.
- `local_base`: reserved for future device2 integration and returns a clean
  skipped result.

## Graph Boundary

The P8 graph facade calls `ExtractorAdapter`, which now delegates to
`get_extractor_backend()`. The graph order remains:

```text
normalize_input -> extract_turn -> validate_turn -> memory_update -> risk_check -> plan_next_action
```

Only `validate_turn` output reaches `MemoryManager.apply_turn()`. Risk authority
still comes after memory update through the risk rule layer, not from LLM or
LoRA candidate fields.

The P9/P10 graph runner also consumes the same backend contract and exports
schema, fallback, and skip metadata for observability.

## Safety Boundaries

- LLM and local LoRA candidates cannot directly own final risk authority.
- High-risk `present` remains sticky.
- Explicit risk negations remain auditable through risk-rule metadata.
- RAG evidence cannot write core facts such as `chief_complaint`, `duration`,
  `risk_flags_status`, or `triggered_rule_ids`.
- No LoRA model weights, adapters, checkpoints, or base model files should be
  committed to normal Git.

## Validation

Run:

```bash
python scripts/verify_p10_extractor_contract.py --json --output artifacts/p10_extractor_contract_validation.json
```

The artifact records backend status, graph integration, schema guard coverage,
safety checks, and LoRA artifact hygiene for P10-M4A.
