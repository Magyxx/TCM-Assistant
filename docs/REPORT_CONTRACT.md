# Report Contract

P1-F0 defines `FinalReportSkeleton` as a deterministic, non-LLM report skeleton.

## Fields

- `session_id`
- `summary`
- `collected_facts`
- `missing_core_fields`
- `risk_status`
- `risk_reasons`
- `evidence_pack`
- `advice`
- `safety_disclaimer`
- `generated_by`
- `schema_version`
- `safety_check`

## Safety

The report skeleton must include a safety disclaimer and must not diagnose, prescribe, discourage care, or replace clinician judgment. Real LLM report generation is out of scope for P1-F0.

## P1-F1 Graph Attachment

When graph RAG is available, report skeletons can include the P1 EvidencePack in `evidence_pack`. This remains deterministic and does not call a real LLM.

## P1-F2 API Exposure

The service and API layers expose the deterministic skeleton as `p1_report_skeleton` on the main API and `report_skeleton` on the P1 wrapper. This is additive; `final_report` remains available on ready reports.

## P1-F5 Report Audit

Productized report paths can expose an additive `report_audit` envelope with schema version `p1_f5_report_audit_v1`. The envelope records safety checks, violations, route, readiness, redacted report/state hashes, and redacted audit flags. It must not include raw report text or raw state text.

Persisted P7 final report snapshots keep the existing safety check shape and add `p1_f5_report_audit` inside `safety_check`.
