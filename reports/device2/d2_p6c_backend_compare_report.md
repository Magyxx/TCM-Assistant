# D2-P6C Backend Compare & Regression Metrics

## 1. Branch and HEAD

- Branch: `feature/device2-local-lora-extractor`
- Validation HEAD: `cef1b0a`

## 2. Recent Commits

- `cef1b0a docs: finalize device2 local lora extractor handoff`
- `c56fbb0 eval: add device2 backend comparison metrics`
- `547bd24 tests: add device2 local lora e2e validation`
- `5c8b123 extractors: integrate local lora backend for device2`
- `3fb8e31 reports: add device2 risk repair light training results`
- `f57e2d2 training: support device2 risk repair light training`
- `683a1e6 chore: document device2 git recovery manifest`
- `a539feb data: add device2 risk repair datasets and configs`
- `980b02e extractor: add deterministic risk projection for device2`
- `1235ba5 eval: add device2 risk failure and metric audit`

## 3. Files Added or Modified

- `scripts/device2/eval_compare_backends.py`
- `scripts/device2/analyze_backend_badcases.py`
- `scripts/device2/verify_d2_p6c_backend_compare.py`
- `tests/test_device2_p6c_backend_compare.py`
- `tests/test_device2_p6c_metrics.py`
- `tests/test_device2_p6c_backend_skip.py`
- `artifacts/device2/d2_p6c_backend_compare_validation.json`
- `artifacts/device2/d2_p6c_backend_metrics.json`
- `artifacts/device2/d2_p6c_backend_predictions.sample.jsonl`
- `artifacts/device2/d2_p6c_backend_badcases.sample.jsonl`
- `reports/device2/d2_p6c_backend_compare_report.md`

## 4. D2-P6A / D2-P6B Summary

D2-P6A connected `local_lora` as an `ExtractorBackend`. D2-P6B proved that `EXTRACTOR_BACKEND=local_lora` runs through `run_consultation_graph`, updates `RunState` after schema pass, blocks writes after schema fail, and keeps final risk status rule-owned.

## 5. Backend Compare Purpose

D2-P6C compares `fake`, `local_base`, `local_lora`, and `cloud_llm` on the same eval cases, producing compact metrics, prediction samples, badcase samples, and a regression report without live service dependency by default.

## 6. Eval Cases

- Source: `builtin_d2_p6c_minimal`
- Count: `7`
- Missing requested paths: `data\sft\eval\eval_extract.jsonl, data\sft\eval\eval_negation.jsonl, data\sft\eval\eval_risk.jsonl`

## 7. Backend Status

| backend | status | case_count | skipped_case_count | skip_reason |
| --- | --- | ---: | ---: | --- |
| fake | passed | 7 | 0 | None |
| local_base | passed_with_badcases | 7 | 0 | None |
| local_lora | passed | 7 | 0 | None |
| cloud_llm | skipped | 0 | 7 | missing_api_key_or_offline_test |

## 8-12. Metrics Table

| backend | json_valid_rate | schema_pass_rate | chief_match | duration_match | negation_accuracy | risk_accuracy | hallucination_rate | fallback_rate | structured_error_rate | avg_ms | p95_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fake | 1.0 | 1.0 | 0.666667 | 0.857143 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.105 | 0.279 |
| local_base | 0.857143 | 0.857143 | 0.666667 | 0.571429 | 1.0 | 1.0 | 0.0 | 0.0 | 0.142857 | 0.13 | 0.204 |
| local_lora | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.099 | 0.154 |
| cloud_llm | null | null | null | null | null | null | null | null | null | null | null |

## 13. local_lora vs local_base

- Comparable: `True`
- Improved metrics: `json_valid_rate, schema_pass_rate, chief_complaint_match_rate, duration_match_rate, structured_error_rate, latency_ms_avg, latency_ms_p95`
- Regressed metrics: `none`
- Notes: `local_lora had no schema/fallback badcases in the mocked default comparison.`

## 14. Badcase Distribution

{"backend_skipped": 7, "invalid_json": 1}

## 15. Schema Fail Guard

- schema fail blocks RunState write: `True`

## 16. Risk Rule Ownership

- risk rule projection: `True`
- local_lora risk claim stripped: `True`

## 17. Live vLLM

- status: `skipped`
- reason: `RUN_LOCAL_VLLM_SMOKE not enabled`

## 18. Full Unittest Discover

`failed_due_preexisting_local_env_blockers`; this is not reported as a full-suite pass.

## 19. Model Weights

none

## 20. Next Step

D2-P7 final docs / resume / release summary.
