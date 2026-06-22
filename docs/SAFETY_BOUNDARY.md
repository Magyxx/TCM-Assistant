# Safety Boundary

Generated: 2026-06-17

TCM-Assistant is an inquiry-information assistant. It is not a diagnosis,
prescription, treatment-plan, or clinician-replacement system.

## Prohibited Output

The system must not output:

- deterministic diagnosis claims
- confirmed diagnosis claims
- prescriptions
- treatment plans
- explicit medication dose instructions
- text claiming to replace clinician judgment
- fabricated conclusions from low-information input

## Required Posture

The system may:

- collect inquiry information
- accumulate structured state
- ask follow-up questions
- identify risk signals
- preserve conservative safety disclaimers
- suggest offline medical evaluation when risk signals are present
- produce structured final reports within the inquiry-information boundary

## Red Flags

High-risk signals remain handled conservatively. The assistant may recommend
offline evaluation, but must not diagnose or prescribe.

## Low-Information Input

When core information is missing, the system should ask for missing fields or
state that information is incomplete. It must not invent a medical conclusion.

## Report Audit

`app/api/report_audit.py` checks generated reports for:

- diagnosis phrases
- confirmed diagnosis phrases
- prescription phrases
- treatment-plan phrases
- drug-dose-like text
- secret-like content
- empty reports
- substitute-medical-advice phrasing

Audit output is JSON-serializable and redacted. It is a lightweight safety gate,
not a medical validator.

## Report Validator

`app/api/report_validator.py` adds a P2.3 non-mutating validator for generated
reports and report snapshots. It reuses `report_audit` and redaction helpers,
then adds structure and state-support checks:

- report JSON serializability
- current `FinalReport` structure for dict reports
- safety audit pass/fail
- no unredacted secret-like content
- no diagnosis, prescription, or treatment-plan phrasing
- red flags are not weakened
- low-information states are not fabricated into complete reports
- urgent triage is not asserted without state support

Persisted report snapshots keep the P1.5 safety flag shape and add a nested
`validator` summary in `safety_flags_json`.

## Secret Redaction

`app/api/redaction.py` redacts secret-like strings and secret-like dictionary
keys before API error output, SQLite JSON persistence, replay/audit artifacts,
and gate output tails.

## P2 Inheritance

P2 work must inherit this boundary. Any future feature that could affect
diagnosis, prescription, treatment-plan, user identity, permissioning, multi-agent
workflows, embeddings, or tool registries requires a separate scope decision.

## P2.5 Delivery Gate

`scripts/run_p2_gate.py` keeps this boundary visible in its JSON artifact through
a `boundary_check` block. The gate automates existing validation only; it does
not add MemoryManager, embedding capability, tool registry, multi-agent workflow,
Web UI, users, permissions, ORM, diagnosis, prescription, or treatment-plan
behavior.
