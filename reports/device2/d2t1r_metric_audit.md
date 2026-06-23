# D2-T1R Metric Audit

Generated at: `2026-06-23T05:19:32+00:00`

## Legacy Metric

* definition: tag contains risk OR gold risk_flags_status is not unknown; exact tri-state string match
* risk_total: `3`
* risk_status_pass: `1`
* risk_status_rate: `0.3333`

## New Metric

* definition: legacy risk case excluding tag/gold conflicts and label-context mismatches; exact tri-state string match
* risk_total: `1`
* risk_status_pass: `1`
* risk_status_rate: `1.0`
* excluded_as_tag_gold_conflict: `1`
* excluded_as_label_context_mismatch: `2`

## Required Confirmations

* Compared field: `risk_flags_status`.
* Match rule: exact normalized tri-state string equality.
* `unknown`, `none`, and `present` are distinct; the legacy subset selection can mix recheck/unknown cases with resolved risk cases.
* `risk_flags_status` is the current TurnOutput field; there is no separate `risk_status` field in SFT TurnOutput.
* Final risk judgement remains the responsibility of the deterministic RiskRuleEngine; the LoRA extractor should provide candidates, flags, and evidence.

## Conclusion

The D2-T1 risk_status_rate uses risk_flags_status, not risk_flags. It is an exact tri-state string match over a tag-derived risk subset. In this dataset the subset includes cases whose tags and gold labels or state context are inconsistent, so the legacy rate mixes model behavior with fixture quality.
