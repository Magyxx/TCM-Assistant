# RAG Evidence Policy

RAG evidence is supporting reference material. It is not user testimony, not a diagnosis, and not an authority to modify the consultation state.

## Allowed Uses
- `retrieved_evidence`
- report impression as cautious background explanation
- report advice as general safety or observation guidance
- citations and evidence notes
- missing knowledge notes

## Forbidden Writes
RAG evidence must not overwrite:
- `chief_complaint`
- `duration`
- `risk_status`
- `risk_rule_ids`
- `explicit_negation`
- `source_turn_id`
- `raw_text`
- `extractor_mode`
- MemoryManager L2 authoritative facts

## Safety Boundary
RAG output must not:
- generate deterministic diagnosis
- prescribe formulas, herbs, medication, dosage, or treatment plans
- replace clinician judgment
- downgrade high-risk status
- treat a knowledge chunk as something the user personally reported

Risk status remains rule-first and audit-driven.
