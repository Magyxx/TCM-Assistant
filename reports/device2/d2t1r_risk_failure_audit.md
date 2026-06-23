# D2-T1R Risk Failure Audit

Generated at: `2026-06-23T05:19:32+00:00`

## Summary

* total risk eval cases: `3`
* passed cases: `1`
* failed cases: `2`
* false negative count: `0`
* false positive count: `0`
* negation false positive count: `0`
* negation false negative count: `0`
* risk keyword extracted but status wrong count: `0`
* status correct but evidence missing count: `0`
* invalid or empty risk field count: `0`
* tag/gold conflict count: `1`
* label/context mismatch count: `2`

## Per Risk Type Accuracy

| Risk type | Total | Passed | Failed | Accuracy |
| --- | ---: | ---: | ---: | ---: |
| high fever | 0 | 0 | 0 | n/a |
| chest pain | 0 | 0 | 0 | n/a |
| dyspnea | 0 | 0 | 0 | n/a |
| hematochezia | 0 | 0 | 0 | n/a |
| hematemesis | 0 | 0 | 0 | n/a |
| altered consciousness | 0 | 0 | 0 | n/a |
| severe abdominal pain | 0 | 0 | 0 | n/a |
| unknown | 3 | 1 | 2 | 0.3333 |

## Top Failed Examples

### sft_F6

* error_type: `tag_gold_conflict`
* suspected_root_cause: risk tag conflicts with gold risk_flags_status
* input: `后来还有点乏力`
* gold risk_flags_status: `none`
* prediction risk_flags_status: `unknown`

### sft_F7

* error_type: `label_context_mismatch`
* suspected_root_cause: gold status cannot be derived from state_json or current user text
* input: `现在感觉好一点了，也没有别的不舒服`
* gold risk_flags_status: `present`
* prediction risk_flags_status: `none`

