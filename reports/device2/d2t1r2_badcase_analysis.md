# D2-T1R2 Badcase Analysis

Generated at: `2026-06-23T06:10:12+00:00`

## Category Counts

| Category | Count |
| --- | ---: |
| invalid_json | 0 |
| schema_failed | 0 |
| risk_false_negative | 2 |
| risk_false_positive | 2 |
| negation_false_positive | 2 |
| negation_false_negative | 0 |
| risk_keyword_extracted_but_status_wrong | 2 |
| status_correct_but_evidence_missing | 0 |
| hallucinated_symptom | 4 |
| diagnosis_or_prescription_violation | 0 |
| core_field_regression | 8 |

## Top 10 Badcases

* `eval_extract` / `sft_F7`: risk_false_negative, core_field_regression
* `eval_risk` / `sft_F7`: risk_false_negative, core_field_regression
* `eval_negation_repair` / `risk_repair_distractor_stool_001`: risk_false_positive, negation_false_positive, risk_keyword_extracted_but_status_wrong, hallucinated_symptom, core_field_regression
* `eval_negation_repair` / `risk_repair_distractor_palpitation_001`: risk_false_positive, negation_false_positive, risk_keyword_extracted_but_status_wrong, hallucinated_symptom, core_field_regression
* `eval_risk_repair` / `risk_repair_present_consciousness_001`: hallucinated_symptom
* `eval_risk_repair` / `risk_repair_present_severe_abdominal_pain_001`: hallucinated_symptom
* `eval_extract` / `sft_G1`: core_field_regression
* `eval_risk_repair` / `risk_repair_mixed_chest_001`: core_field_regression
* `eval_risk_repair` / `risk_repair_mixed_dyspnea_001`: core_field_regression
* `eval_negation_repair` / `risk_repair_distractor_chest_001`: core_field_regression
