# D2-T1R2 Evaluation Report

Generated at: `2026-06-23T06:10:12+00:00`

## eval_extract

* source: `data/sft/processed/sft_report_turn_extract_val.jsonl`
* source kind: `file`
* D2-T1 sample prediction: `artifacts/device2/predictions/d2t1r2_d2t1_eval_extract_sample.jsonl`
* D2-T1R2 sample prediction: `artifacts/device2/predictions/d2t1r2_d2t1r2_eval_extract_sample.jsonl`

| Metric | Value |
| --- | ---: |
| total | 4 |
| exact_core_rate | 0.5 |
| schema_pass_rate | 1.0 |
| json_valid_rate | 1.0 |
| risk_status_rate | 0.6667 |
| coherent_risk_status_rate | 0.6667 |
| risk_false_negative_count | 1 |
| risk_false_positive_count | 0 |
| negation_accuracy | 1.0 |
| hallucination_rate | 0.0 |
| diagnosis_or_prescription_violation_count | 0 |

## eval_negation

* source: `data/sft/processed/sft_report_turn_extract_val.jsonl`
* source kind: `derived_from_original_extract`
* D2-T1 sample prediction: `artifacts/device2/predictions/d2t1r2_d2t1_eval_negation_sample.jsonl`
* D2-T1R2 sample prediction: `artifacts/device2/predictions/d2t1r2_d2t1r2_eval_negation_sample.jsonl`

| Metric | Value |
| --- | ---: |
| total | 1 |
| exact_core_rate | 1.0 |
| schema_pass_rate | 1.0 |
| json_valid_rate | 1.0 |
| risk_status_rate | 1.0 |
| coherent_risk_status_rate | 1.0 |
| risk_false_negative_count | 0 |
| risk_false_positive_count | 0 |
| negation_accuracy | 1.0 |
| hallucination_rate | 0.0 |
| diagnosis_or_prescription_violation_count | 0 |

## eval_risk

* source: `data/sft/processed/sft_report_turn_extract_val.jsonl`
* source kind: `derived_from_original_extract`
* D2-T1 sample prediction: `artifacts/device2/predictions/d2t1r2_d2t1_eval_risk_sample.jsonl`
* D2-T1R2 sample prediction: `artifacts/device2/predictions/d2t1r2_d2t1r2_eval_risk_sample.jsonl`

| Metric | Value |
| --- | ---: |
| total | 3 |
| exact_core_rate | 0.6667 |
| schema_pass_rate | 1.0 |
| json_valid_rate | 1.0 |
| risk_status_rate | 0.6667 |
| coherent_risk_status_rate | 0.6667 |
| risk_false_negative_count | 1 |
| risk_false_positive_count | 0 |
| negation_accuracy | 1.0 |
| hallucination_rate | 0.0 |
| diagnosis_or_prescription_violation_count | 0 |

## eval_risk_repair

* source: `data/sft/eval/eval_risk_repair.jsonl`
* source kind: `file`
* D2-T1 sample prediction: `artifacts/device2/predictions/d2t1r2_d2t1_eval_risk_repair_sample.jsonl`
* D2-T1R2 sample prediction: `artifacts/device2/predictions/d2t1r2_d2t1r2_eval_risk_repair_sample.jsonl`

| Metric | Value |
| --- | ---: |
| total | 12 |
| exact_core_rate | 0.8333 |
| schema_pass_rate | 1.0 |
| json_valid_rate | 1.0 |
| risk_status_rate | 1.0 |
| coherent_risk_status_rate | 1.0 |
| risk_false_negative_count | 0 |
| risk_false_positive_count | 0 |
| negation_accuracy | 1.0 |
| hallucination_rate | 0.1667 |
| diagnosis_or_prescription_violation_count | 0 |

## eval_negation_repair

* source: `data/sft/eval/eval_negation_repair.jsonl`
* source kind: `file`
* D2-T1 sample prediction: `artifacts/device2/predictions/d2t1r2_d2t1_eval_negation_repair_sample.jsonl`
* D2-T1R2 sample prediction: `artifacts/device2/predictions/d2t1r2_d2t1r2_eval_negation_repair_sample.jsonl`

| Metric | Value |
| --- | ---: |
| total | 8 |
| exact_core_rate | 0.625 |
| schema_pass_rate | 1.0 |
| json_valid_rate | 1.0 |
| risk_status_rate | 0.75 |
| coherent_risk_status_rate | 0.75 |
| risk_false_negative_count | 0 |
| risk_false_positive_count | 2 |
| negation_accuracy | 0.75 |
| hallucination_rate | 0.25 |
| diagnosis_or_prescription_violation_count | 0 |

