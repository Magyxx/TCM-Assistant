# P12 Service Readiness Plan

P12 turns the P11 safety and workflow contracts into a small, repeatable service
readiness loop. It does not add diagnosis, prescription, live vLLM defaults,
model training, frontend work, or production deployment.

## Milestones

| Milestone | Scope | Validation |
| --- | --- | --- |
| P12-M1 | Inventory the existing FastAPI, service, storage, session, report, eval, and OpenAPI surfaces. | `scripts/verify_p12_service_baseline.py` |
| P12-M2 | Lock the minimum session, turn, state, and health API contract. | `scripts/verify_p12_api_contract.py` |
| P12-M3 | Lock SQLite session, turn, state, report, and audit persistence using temporary DBs in tests. | `scripts/verify_p12_persistence.py` |
| P12-M4 | Lock report, eval, extended health, and safety-boundary API behavior. | `scripts/verify_p12_report_eval_api.py` |
| P12-M5 | Aggregate P12 regression status and export OpenAPI under `artifacts/p12/`. | `scripts/verify_p12_service_regression.py` |
| P12-M6 | Produce the pre-merge gate report without merging to `main`. | `docs/P12_MERGE_GATE_REPORT.md` |

## Boundaries

- Default API smoke tests use `fake` or safe fallback extraction.
- Optional cloud, local vLLM, and local LoRA backends must skip with explicit reasons when unavailable.
- Risk status remains owned by deterministic risk rules.
- RAG evidence may support reports but must not overwrite core inquiry state.
- Final reports remain bounded by the no-diagnosis and no-prescription safety contract.
- SQLite is the local default; PostgreSQL remains schema-ready only for this stage.
- Tests and verifiers use temporary databases and do not commit runtime DB files.

## Next Landing Order

1. Service inventory baseline.
2. Session/turn/state/health API smoke contract.
3. SQLite persistence and replay contract.
4. Report/eval/extended health API contract.
5. Service regression and OpenAPI artifact.
6. Merge gate report and branch push for review.
