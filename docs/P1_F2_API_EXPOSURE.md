# P1-F2 API Service Exposure

P1-F2 exposes the P1-F1 evidence pack and deterministic report skeleton through the service and HTTP API surfaces.

## Behavior

- `ConsultationService.run_turn()` returns `p1_evidence_pack` and `p1_report_skeleton`.
- `ConsultationService.get_report()` returns the same P1 payloads after state persistence and reload.
- `app.api.main:app` exposes `p1_evidence_pack` and `p1_report_skeleton` on turn and report responses.
- `app.api.app:app` maps those fields to the productization wrapper names `evidence_pack` and `report_skeleton`.
- The P1 wrapper uses the deterministic P1 report skeleton as `skeleton` when it is available.

## Compatibility

All fields are additive. Existing required response fields remain unchanged:

- `final_report` stays available on ready reports.
- `ready` / `report_available` semantics are unchanged.
- `next_question` remains available; a completed P1 wrapper turn now uses `next_action=review_summary`.

## Safety

The exposed payloads are still sanitized through the existing redaction path. P1-F2 does not add a real LLM, embedding service, vectorstore, PostgreSQL dependency, or deployment requirement.

## Artifact

`scripts/verify_p1_f2_api_exposure.py` writes `artifacts/p1_f2_api_exposure_validation.json`.
