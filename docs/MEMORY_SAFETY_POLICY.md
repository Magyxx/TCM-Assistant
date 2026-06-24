# Memory Safety Policy

## Product Boundary
TCM-Assistant is a consultation-support assistant. It helps organize chief complaint, duration, associated symptoms, sleep, appetite, stool/urine, risk signals, and follow-up questions. It must not provide deterministic diagnosis, prescribe medicine, or replace clinician judgment.

## Write Authority
- LLM extraction can propose candidate facts only.
- `TurnOutput` must pass Pydantic schema validation before any field can enter L2.
- Deterministic risk rules are the authority for risk status and risk rule IDs.
- RAG evidence is read-only for core state.
- L3 summaries are generated from L2 facts only.

## Field Traceability
Every L2 fact must retain:
- `source_turn_id`
- `raw_text`
- `extractor_mode`
- `confidence`
- `source_kind`

Every merge decision must add an audit event containing the previous value, candidate value, source, confidence, action, result, and reason.

## Merge Rules
- Empty values cannot overwrite non-empty values.
- Lower-confidence candidates cannot overwrite higher-confidence facts unless the user explicitly corrects the field.
- LLM candidates cannot write `risk_flags_status`, `risk_flags`, `risk_reasons`, or `triggered_rule_ids`.
- `risk_flags_status="present"` is sticky and cannot be downgraded by ordinary later text.
- Explicit negation is stored as `explicit_negation=True`; it is not treated as unknown.
- RAG evidence cannot overwrite `chief_complaint`, `duration`, `risk_status`, or `risk_rule_ids`.

## L4 Privacy
P8-M1 does not store real user history in L4. L4 is an interface for knowledge or anonymized experience only and must not contain raw patient dialogue, phone numbers, IDs, emails, or other patient identifiers.

## Operational Notes
The memory layer is additive. P7 freeze, device2 SFT/LoRA branches, and the old SFT pipeline are not modified. The RunState bridge exists to keep older workflow code compatible while P8 introduces traceable facts.
