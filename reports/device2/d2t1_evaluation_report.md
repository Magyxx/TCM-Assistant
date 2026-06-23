# D2-T1 Evaluation Report

Generated at: `2026-06-23T01:38:19+00:00`

Status: `caution`

## local_base

| Metric | Value |
| --- | ---: |
| total | 4 |
| exact_core_rate | 0.0 |
| schema_pass_rate | 1.0 |
| risk_status_rate | 0.3333 |
| negation_risk_status_rate | 1.0 |
| chief_complaint_rate | 0.0 |
| duration_rate | 0.0 |
| symptoms_status_rate | 0.75 |
| risk_flags_status_rate | 0.5 |

## local_lora

| Metric | Value |
| --- | ---: |
| total | 4 |
| exact_core_rate | 0.5 |
| schema_pass_rate | 1.0 |
| risk_status_rate | 0.3333 |
| negation_risk_status_rate | 1.0 |
| chief_complaint_rate | 1.0 |
| duration_rate | 1.0 |
| symptoms_status_rate | 1.0 |
| risk_flags_status_rate | 0.5 |

## Comparison

```json
{
  "exact_core_rate_delta": 0.5,
  "schema_pass_rate_delta": 0.0,
  "risk_status_rate_delta": 0.0,
  "negation_risk_status_rate_delta": 0.0
}
```

## Badcases

* `sft_F6` failed_fields=['risk_flags_status']
* `sft_F7` failed_fields=['risk_flags_status']
