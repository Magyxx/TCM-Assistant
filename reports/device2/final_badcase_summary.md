# Device2 Final Badcase Summary

## Source

- Source artifact: `artifacts/device2/d2_p6c_backend_badcases.sample.jsonl`
- Related metrics: `artifacts/device2/d2_p6c_backend_metrics.json`
- Eval case source: `builtin_d2_p6c_minimal`
- Eval case count: `7`

## Badcase Count

The D2-P6C badcase sample contains `8` rows:

- `1` local_base invalid JSON row
- `7` cloud_llm skipped rows
- `0` local_lora rows

## Failure Type Distribution

| Failure type | Count | Meaning |
| --- | ---: | --- |
| `invalid_json` | 1 | Backend returned text that could not be parsed as a JSON object |
| `backend_skipped` | 7 | Backend was intentionally skipped in the default offline/local verification path |

## local_base Main Failure

`local_base` has one concrete badcase:

- `case_id`: `schema_fail_mock_001`
- `backend`: `local_base`
- `failure_type`: `invalid_json`
- `raw_output`: `not json`
- `error_message`: `json_object_start_not_found`
- `schema_pass`: `false`

This is a model/backend output-format issue in the mocked regression path. The expected guard behavior is to reject the candidate and avoid writing invalid state.

## local_lora Failures

`local_lora` has no badcases in the D2-P6C sample. Its D2-P6C metrics show:

- `json_valid_rate`: `1.0`
- `schema_pass_rate`: `1.0`
- `chief_complaint_match_rate`: `1.0`
- `duration_match_rate`: `1.0`
- `risk_flag_accuracy`: `1.0`
- `structured_error_rate`: `0.0`

This should be read as local regression evidence over seven built-in cases, not a broad quality claim.

## Schema Fail Sample

The schema-fail representative is the local_base `schema_fail_mock_001` badcase. It demonstrates the expected failure mode:

```text
raw_output: not json
json_valid: false
schema_pass: false
failure_type: invalid_json
error_message: json_object_start_not_found
```

## Hallucination Sample

No hallucination badcase appears in the D2-P6C badcase sample. The metric summary records `hallucination_rate=0.0` for `fake`, `local_base`, and `local_lora`, with `cloud_llm` skipped.

The absence of a hallucination sample is limited by the small seven-case eval set.

## Risk False Positive / False Negative Sample

No risk false positive or false negative appears in the D2-P6C metrics:

- `fake`: false positives `0`, false negatives `0`
- `local_base`: false positives `0`, false negatives `0`
- `local_lora`: false positives `0`, false negatives `0`
- `cloud_llm`: skipped

Risk ownership remains with deterministic rules, not with the LoRA candidate.

## Model Issues

The concrete model/backend issue in the sample is output-structure instability for `local_base`: it can emit invalid JSON under the mocked schema-fail case.

## Eval Set Limitations

The following limitations come from eval size and availability:

- D2-P6C used only `builtin_d2_p6c_minimal`
- The set contains seven cases
- Requested `eval_extract.jsonl`, `eval_negation.jsonl`, and `eval_risk.jsonl` are absent
- `cloud_llm` is skipped by default, so it contributes skip rows rather than quality failures

## Recommended Eval Expansion

Add separate JSONL suites before making stronger claims:

- `eval_extract.jsonl`: broader chief complaint, duration, symptoms, sleep, appetite, stool/urine coverage
- `eval_negation.jsonl`: explicit negation, double negation, symptom absence, and red-flag denial cases
- `eval_risk.jsonl`: high-risk positive, high-risk negated, ambiguous risk, and multi-risk cases

Each suite should preserve small sample artifacts in Git and keep full predictions outside the repository.

