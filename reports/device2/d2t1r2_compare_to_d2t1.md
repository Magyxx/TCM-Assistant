# D2-T1R2 Compare To D2-T1

Generated at: `2026-06-23T06:10:12+00:00`

Acceptance status: `ok`

## Metrics

| Metric | D2-T1 | D2-T1R2 | Conclusion |
| --- | ---: | ---: | --- |
| exact_core_rate | 0.5 | 0.5 | unchanged |
| schema_pass_rate | 1.0 | 1.0 | unchanged |
| json_valid_rate | 1.0 | 1.0 | unchanged |
| risk_status_rate | 0.3333 | 0.6667 | improved |
| coherent_risk_status_rate | 0.3333 | 0.6667 | improved |
| risk_false_negative_count | 10 | 0 | improved |
| risk_false_positive_count | 0 | 0 | unchanged |
| negation_accuracy | 0.625 | 0.75 | improved |
| hallucination_rate | 0.0 | 0.0 | unchanged |
| diagnosis_or_prescription_violation_count | 0 | 0 | unchanged |

## Notes

* D2-T1 file metrics are from artifacts/device2/d2t1_metrics.json; repair-set baseline is freshly evaluated with the D2-T1 adapter.
* original eval_risk/eval_negation are derived subsets of sft_report_turn_extract_val.jsonl because standalone files are absent.
