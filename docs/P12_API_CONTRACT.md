# P12 Session And Turn API Contract

P12-M2 locks the minimum service loop already exposed by `app.api.main:app`.

## Required Routes

| Route | Contract |
| --- | --- |
| `GET /health` | Returns service status. With `extended=true`, includes storage status, backend matrix summary, P11 contract availability, and live vLLM skipped/enabled status. |
| `POST /sessions` | Creates a session without login. The P12 smoke path uses `fake` extraction and temporary SQLite paths. |
| `POST /sessions/{session_id}/turn` | Accepts `user_input`, routes through the extractor/workflow/schema/risk path, persists the turn, and returns `session_id`, `turn_id`, state summary or next action, risk status, and safety disclaimer. |
| `GET /sessions/{session_id}/state` | Reads the persisted state after a turn and returns turn count, missing core fields, risk rule ids, and public state. |

## Safety Conditions

- Default smoke requests use `fake` extraction.
- Optional live backends are not required for API readiness.
- High-risk input must still produce deterministic risk-rule flags.
- Responses must not introduce diagnosis or prescription claims.
- The safety disclaimer may mention diagnosis and prescription only as boundaries.

The verifier writes `artifacts/p12/api_contract.json`.
