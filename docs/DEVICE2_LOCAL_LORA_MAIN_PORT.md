# D2-MP1 Device2 Local LoRA Main Port

## Stage Goal

D2-MP1 is a minimal port of Device2 local LoRA/vLLM extractor capability onto the current `main` extractor interface. It is not a merge of `origin/feature/device2-local-lora-extractor`.

The current base is:

- `main`: `56f69eb2693fe3eecd4f1baf43603798d3b2aff9`
- Device2 reference branch: `origin/feature/device2-local-lora-extractor`
- Device2 reference head: `8150e3cafec233f0afebcf4f67626b0a7224db21`
- Port branch: `port/device2-local-lora-current-interface`

## Why D2-MP0 Was Blocked

D2-MP0 showed that the Device2 branch cannot be merged cleanly into current `main`. Conflicts included `.env.example`, `app/extractors/*`, `app/rules/risk_rules.py`, `artifacts/secret_scan_result.json`, and `tests/test_extractor_router.py`.

The more important blocker was interface drift. Device2 used older backend shapes such as `BackendResult` and call order like `extract_turn(state, user_input)`, while current `main` uses `ExtractorResult` and `extract(user_input, *, state=...)`.

## Why Not Direct Merge Device2

The Device2 branch is broader than this milestone. It contains local model serving work, old router assumptions, risk-rule changes, smoke scripts, and environment examples. Direct merge would mix extractor backend work with graph/risk/session contract changes.

D2-MP1 therefore ports only the safe extractor backend portion and leaves training, checkpoints, adapters, and broader risk-rule changes outside the branch.

## Current Main Extractor Protocol

Current `main` exposes `ExtractorBackend` in `app/extractors/base.py`.

The backend entry point is:

```python
extract(user_input, *, state=None, memory=None, config=None, session_id=None, turn_id=None) -> ExtractorResult
```

The compatibility helper `extract_turn(user_input, state=None) -> TurnOutput` still exists for callers that have not moved to `ExtractorResult`, but it is not the old Device2 call order and the local LoRA port does not require `extract_turn(state, user_input)`.

## Local LoRA Adaptation

`LocalLoRAExtractorBackend` and `LocalVLLMExtractorBackend` both use the current protocol and return `ExtractorResult`.

The flow is:

1. Build a bounded system/user message for a single-turn `TurnOutput` JSON candidate.
2. Call an OpenAI-compatible `/v1/chat/completions` endpoint.
3. Extract assistant message content.
4. Parse JSON, including bounded code-fence/object repair.
5. Validate with the current `TurnOutput` Pydantic schema.
6. Return `ExtractorResult` with metadata including `backend`, `base_url`, `model`, `json_valid`, `schema_pass`, `fallback_used`, `live_vllm_used`, and error fields when applicable.

Malformed JSON or schema mismatch does not mutate `RunState`. The extractor returns an auditable fallback/error metadata path instead.

## vLLM OpenAI-Compatible Configuration

The default `.env.example` values are placeholders only:

```env
EXTRACTOR_BACKEND=local_lora
LOCAL_LLM_BASE_URL=http://127.0.0.1:8000/v1
LOCAL_LLM_MODEL=tcm-extractor-lora
LOCAL_LLM_API_KEY=dummy
LOCAL_LLM_TIMEOUT_SECONDS=30
RUN_LOCAL_VLLM_SMOKE=0
```

`LOCAL_LLM_API_KEY=dummy` is not a real secret. Local vLLM deployments often ignore the key, but the OpenAI-compatible client can still send a bearer header when a local service expects one.

## Default Tests Do Not Require GPU or vLLM

Default unit tests use mock OpenAI-compatible responses or skip live smoke coverage when `RUN_LOCAL_VLLM_SMOKE` is not enabled. This keeps CI and normal workstation validation independent of GPU, vLLM, model weights, adapters, or checkpoint files.

## Pydantic and Risk Boundary

The LoRA model output is only a candidate `TurnOutput`. It cannot bypass Pydantic validation, and it cannot decide final risk authority.

`risk_flags` and `risk_flags_status` from the extractor remain candidate fields. The main graph and risk-rule layer still own final risk evaluation, triggered rule IDs, and high-risk stickiness.

## Not Ported In D2-MP1

The following Device2 content is intentionally not ported:

- Training scripts: deferred.
- Large evaluation datasets: deferred.
- Device2 edits to `app/rules/risk_rules.py`: deferred.
- `artifacts/secret_scan_result.json` from Device2: not ported.
- Base model weights, LoRA adapters, checkpoints, and local `.env` files: not ported.
- Old router and `BackendResult` contract: not ported.

## D2-MP2 Pre-Merge Direction

D2-MP2 should treat this port branch as the source of truth for merge precheck. Recommended next checks:

1. Re-run full unit, secret, artifact, and release/hardening gates.
2. Confirm no tracked model/adapter/checkpoint/env payloads.
3. Review `ExtractorResult` metadata and risk-boundary behavior in a PR.
4. Optionally run live vLLM smoke only with `RUN_LOCAL_VLLM_SMOKE=1` in an isolated local environment.
5. Merge only if the port branch remains narrow and does not change graph/risk/session ownership.
