# P12 Report Eval And Health API Contract

P12-M4 verifies the existing report, eval, and health endpoints as stable service
contracts.

## Routes

| Route | Contract |
| --- | --- |
| `POST /sessions/{session_id}/report` | Persists and returns the current safe report when ready. |
| `GET /sessions/{session_id}/report` | Reads the current report state without requiring a write. |
| `POST /eval/final` | Accepts a lightweight no-live-model smoke path for API contract validation. |
| `GET /health?extended=true` | Returns service, storage, backend matrix, P11 contract availability, and live vLLM skipped/enabled status. |
| `GET /sessions/{session_id}/turns` | Provides a replay-friendly turn listing. |

## Safety

- Report responses must not introduce diagnosis or prescription claims.
- High-risk cases must preserve urgent triage guidance.
- RAG evidence, when present, must include source or chunk metadata.
- Eval smoke does not require cloud keys, live vLLM, local LoRA, or external network.

The verifier writes `artifacts/p12/report_eval_api_contract.json`.
