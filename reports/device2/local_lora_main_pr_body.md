## Summary

- Port Device2 local_lora/local_vllm extractor to current ExtractorResult interface.
- Register local_lora and local_vllm backends in the current router.
- Preserve risk rules as final safety fallback.
- Add schema/malformed JSON/router guards and port verification script.

## Validation

- compileall: passed
- unittest: passed, 438 tests, 1 skipped
- secret_scan: passed, finding_count=0
- verify_device2_local_lora_port: passed
- D2-MP2 merge simulation: passed
- release packaging check: passed, 12/12 checks

## Safety / Scope

- No model weights committed.
- No adapter/checkpoint committed.
- No .env or secrets committed.
- No BackendResult in port runtime/test code.
- No default GPU/vLLM dependency.
- live vLLM smoke skipped unless RUN_LOCAL_VLLM_SMOKE is enabled.

## Merge Risk

- risk level: ok
- known skipped items:
  - live vLLM smoke skipped by default because RUN_LOCAL_VLLM_SMOKE is not enabled
  - broad release_candidate_audit / p2_p10_release_hardening aggregate gates skipped for D2-MP2 scope after full unittest, secret scan, port verifier, merge simulation, and packaging check passed
