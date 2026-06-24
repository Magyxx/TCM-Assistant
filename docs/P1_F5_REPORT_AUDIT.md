# P1-F5 Report Safety Redaction Audit

P1-F5 adds a report audit envelope to the post-P8 productization path.

The goal is to prove that report-like outputs exposed through the API are
checked for safety boundaries, secret leakage, and traceable audit metadata
without requiring a real LLM or external report runtime.

## Scope

P1-F5 covers:

- report skeleton safety checks.
- report audit envelopes for productized turn/report responses.
- P1 wrapper report response audit exposure.
- P7 persisted final report safety check enrichment.
- secret redaction proof through hashed report/state payloads.
- diagnosis, prescription, treatment-plan, discouraged-care, and drug-dose-like
  phrase detection.

## API Shape

The following productization responses may include an additive `report_audit`
object:

- `POST /sessions/{session_id}/turn`
- `GET /sessions/{session_id}/report`
- `GET /reports/{session_id}`

The audit object uses schema version `p1_f5_report_audit_v1` and includes:

- `status`
- `passed`
- `route`
- `ready`
- `checks`
- `violations`
- `api_audit_rules`
- `api_audit_flags`
- `redacted_report_hash`
- `redacted_state_hash`

The audit object does not include raw report text or raw state text.

## Storage

`record_report()` keeps the existing `validate_report()` result and adds
`p1_f5_report_audit` inside the stored `safety_check` JSON.

This preserves the earlier `passed` field while making the report snapshot
traceable to the P1-F5 audit schema.

## Boundary Statement

P1-F5 does not add report generation capability. It only audits deterministic
or already-generated report payloads.

It does not introduce:

- diagnosis output.
- prescription output.
- treatment-plan output.
- real LLM report generation.
- local LoRA report generation.
- external report service calls.
- Device2 LoRA merge.

## Validation

Run:

```powershell
python scripts/verify_p1_f5_report_audit.py
```

Machine-readable output:

```powershell
python scripts/verify_p1_f5_report_audit.py --json --output artifacts/p1_f5_report_audit_validation.json
```

Acceptance requires:

- direct audit flags unsafe report text.
- unsafe audit payloads redact synthetic secrets.
- main API turn/report responses expose passing `report_audit`.
- P1 wrapper report response exposes passing `report_audit`.
- persisted P7 final report safety checks include passing `p1_f5_report_audit`.
- no real LLM or external report runtime is required.
