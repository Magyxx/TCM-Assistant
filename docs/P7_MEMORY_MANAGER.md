# P7 Memory Manager

## Four Layers
- L1 `recent_turns`: bounded recent turn previews for context.
- L2 `structured_facts`: authoritative facts derived from validated Pydantic RunState fields, with `source_turn_id`, optional text span, confidence, timestamp and schema version.
- L3 `case_summary`: generated only from L2 facts, including missing fields and risk status.
- L4 `experience_retrieval`: approved knowledge, anonymous failure samples and synthetic eval cases only.

## Write Rules
LLM output can propose facts but cannot directly overwrite authoritative state. Risk status is written by deterministic risk rules. High-risk `present` is sticky. Negated risk is represented as `none`/negated, not as missing. RAG evidence cannot overwrite core inquiry fields.

## Privacy
L4 rejects PII and raw patient text. L1 may contain redacted preview text for the active session, while long-term L4 storage remains knowledge/eval-only.
