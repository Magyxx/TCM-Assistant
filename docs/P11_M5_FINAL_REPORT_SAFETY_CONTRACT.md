# P11-M5 FinalReport Safety Contract

P11-M5 stabilizes the final report boundary after the post-LoRA runtime and RAG
evidence path are already available. It does not introduce new diagnosis,
prescription, treatment planning, or live model behavior.

## Report Schema

The main report schema is `app.schemas.report_schemas.FinalReport`.

The P11 mainline report contract requires these fields to remain available:

- `summary`
- `impression`
- `advice`
- `triage_level`
- `info_complete`
- `missing_core_fields`
- `followup_needed`
- `safety_disclaimer`
- `evidence_citations`
- `evidence_ids`
- `citation_coverage`
- `metadata`

`triage_level` is limited to `observe`, `followup`, and `urgent_visit`.

## Safety Checks

There are two active guard layers:

- `app.report.safety.check_report_safety` blocks diagnosis, prescription,
  clinician-replacement, discouraged-care, and dose-like text patterns.
- `app.safety.report_safety.safety_post_check_report` rewrites forbidden
  final-report terms, preserves structured fields, and adds the standard safety
  boundary text.

The post-check metadata must include:

- `safety_post_check_issues`
- `safety_rewrite_used`
- `safety_violation_type`
- `safety_boundary`

## High-Risk Routing

High-risk reports must preserve `triage_level="urgent_visit"` and must keep
offline medical evaluation guidance visible after post-check. Safe urgent-care
guidance should not be marked as rewritten merely because the standard safety
boundary was appended.

## Evidence Citations

Safety post-check must preserve:

- `evidence_ids`
- `evidence_citations`
- `citation_coverage`
- citation metadata written by `app.rag.citation.attach_citations_to_report`

Evidence may support explanation and safety boundaries, but it must not bypass
the report safety checker.

## Verification

Run:

```powershell
python -m compileall -q app scripts tests
python -m unittest discover -s tests
python scripts/verify_p11_report_safety_contract.py --json --output artifacts/p11/report_safety_contract.json
```

The M5 artifact is `artifacts/p11/report_safety_contract.json`.
