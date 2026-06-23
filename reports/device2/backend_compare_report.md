# D2-P5B Backend Comparison Report

Generated at: `2026-06-23T11:52:22+00:00`

Status: `caution`

## Backend Status

| backend | status | case_count | json_valid_rate | schema_pass_rate | fallback_rate | avg_latency_ms | p95_latency_ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| fake | ok | 20 | 1.0 | 1.0 | 0.0 | 276.309 | 276.433 |
| local_base | caution | 20 | 1.0 | 0.55 | 0.0 | 2320.155 | 2815.711 |
| local_lora | ok | 20 | 1.0 | 1.0 | 0.0 | 1843.028 | 2220.492 |
| cloud_llm | skipped | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## Case Source

* case_source: `builtin`
* builtin_cases: `True`
* gold_limited: `True`

## local_lora vs local_base

local_lora improved schema_pass_rate versus local_base.

## local_lora Badcase

none

## Next Training Notes

* Do not infer accuracy from limited gold labels.
* If local_lora is not better than local_base, prioritize JSON stability, schema completeness, negation handling, and high-risk preservation in the next data round.
