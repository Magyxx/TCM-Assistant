# D2-MP1 Local LoRA Port Report

## Summary

- Status: `ok`
- Port branch: `port/device2-local-lora-current-interface`
- Main base HEAD: `56f69eb2693fe3eecd4f1baf43603798d3b2aff9`
- Source Device2 branch: `origin/feature/device2-local-lora-extractor`
- Source Device2 HEAD: `8150e3cafec233f0afebcf4f67626b0a7224db21`
- Merge recommendation: proceed to D2-MP2 PR/merge precheck with caution-level human review.

## Ported Files

- `.env.example`
- `app/extractors/local_lora_extractor.py`
- `app/extractors/openai_compatible_client.py`
- `app/extractors/router.py`
- `app/extractors/__init__.py`
- `tests/test_extractor_contract.py`
- `tests/test_extractor_router.py`
- `tests/test_local_lora_extractor.py`
- `tests/test_local_lora_schema_guard.py`
- `scripts/verify_device2_local_lora_port.py`
- `docs/DEVICE2_LOCAL_LORA_MAIN_PORT.md`
- `docs/DEVICE2_VLLM_SERVING.md`
- `reports/device2/local_lora_port_report.md`
- `artifacts/device2_local_lora_port_validation.json`

## Not Ported From Device2

- Old `BackendResult` result type: not compatible with current `main`.
- Old `extract_turn(state, user_input)` call order: replaced by current `extract(user_input, *, state=...)`.
- Device2 router model: current `app/extractors/router.py` remains authoritative.
- Device2 `app/rules/risk_rules.py` changes: deferred to avoid changing risk authority in this port.
- Device2 `artifacts/secret_scan_result.json`: not ported.
- Training scripts and large eval data: deferred.
- vLLM, PEFT, TRL, bitsandbytes dependencies: not added to default requirements.
- Base model weights, LoRA adapters, checkpoints, local `.env`, and secrets: not ported.

## Interface Compatibility

`LocalLoRAExtractorBackend` and `LocalVLLMExtractorBackend` implement the current `ExtractorBackend` contract:

```python
extract(user_input, *, state=None, memory=None, config=None, session_id=None, turn_id=None) -> ExtractorResult
```

Both return `ExtractorResult` and attach audit metadata for:

- `backend`
- `base_url`
- `model`
- `json_valid`
- `schema_pass`
- `fallback_used`
- `live_vllm_used`
- `error_type`
- `skip_reason`

No `BackendResult` type is introduced.

## Tests And Verification

- `python -m compileall -q app scripts tests`: passed.
- `python -m unittest discover -s tests`: passed, `438` tests, `1` skipped.
- `python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json`: passed, `finding_count=0`.
- `python scripts/verify_device2_local_lora_port.py --json --output artifacts/device2_local_lora_port_validation.json`: passed, `status=ok`.
- Optional release/hardening scripts: not run in this stage; D2-MP2 should rerun them before PR/merge.

## Risk Boundary

The local LoRA/vLLM extractor produces only a candidate `TurnOutput`. Its `risk_flags` and `risk_flags_status` do not own final risk authority.

The D2-MP1 verifier confirms a mocked local LoRA output that attempts to clear high-risk text still results in main graph risk rules setting final risk to `present`.

## Skipped Items

- Live vLLM smoke: skipped by default because `RUN_LOCAL_VLLM_SMOKE=0`.
- GPU/model loading: not required and not executed.
- Training/eval pipeline: not executed.

## D2-MP2 Recommendation

Proceed to D2-MP2 only as a PR/merge precheck from this port branch into `main`. D2-MP2 should rerun full verification, inspect generated artifacts, confirm no forbidden model/env payloads are tracked, and review that graph/risk/session contracts remain unchanged.
