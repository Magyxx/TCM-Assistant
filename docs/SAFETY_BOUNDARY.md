# Safety Boundary

TCM-Assistant is a structured inquiry assistant. It is not a diagnosis system, does not prescribe, and does not replace clinicians.

## Hard Rules
- No definitive diagnosis.
- No prescriptions, formulas, herb dosages, or medication plans.
- No replacement of offline medical evaluation.
- High-risk signals prompt offline care.
- RAG only supports explanation, question selection, and safety reminders.
- LLM output cannot overwrite risk state or risk rule ids.
- LoRA output cannot overwrite risk state or risk rule ids.
- Logs must not expose Authorization headers, API keys, secret-like values, full `.env` content, or raw private user text by default.

## High-Risk Examples
Chest pain, breathing difficulty, blood in stool, vomiting blood, persistent high fever, severe abdominal pain, confusion, fainting, or abnormal consciousness must keep deterministic risk handling authoritative.

