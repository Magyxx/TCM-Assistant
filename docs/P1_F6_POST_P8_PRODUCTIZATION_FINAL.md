# P1-F6 Post-P8 Productization Final

P1-F6 closes the follow-up project that started after P8-M3 completed. It is a
final aggregation and acceptance layer for the post-P8 P1-F0 through P1-F5
route, not a new clinical behavior layer.

## Scope

P1-F6 verifies and records:

- P1-F0 productization foundation.
- P1-F1 BM25 EvidencePack graph/report integration.
- P1-F2 API exposure for evidence pack and report skeleton fields.
- P1-F3 tool audit trace correlation.
- P1-F4 post-P8 productization gate.
- P1-F5 report safety, redaction, and audit envelope.
- P8 memory, graph, and structured extractor baselines.
- secret scan and `git diff --check`.
- focused post-P8 unit regression.

The older P1.1-P1.6 gate remains historical context only. It is not
authoritative for this route because it treated MemoryManager and Tool Registry
as non-goals, while the post-P8 route accepts them as bounded, tested baseline
components.

## Command

```powershell
python scripts/verify_p1_f6_post_p8_productization_final.py
```

Machine-readable output:

```powershell
python scripts/verify_p1_f6_post_p8_productization_final.py --json --output artifacts/p1_f6_post_p8_productization_final.json
```

For a slower broad regression run, add:

```powershell
python scripts/verify_p1_f6_post_p8_productization_final.py --full-unittest
```

## Artifact

The final artifact is:

- `artifacts/p1_f6_post_p8_productization_final.json`

It records command results, artifact status summaries, explicit boundary
decisions, failed commands, failed artifacts, current branch, current commit,
and a completion decision for the post-P8 productization route.

## Boundary Statement

P1-F6 preserves these limits:

- no real LLM is required.
- no local LoRA runtime is required.
- no embedding model, vector store, or PostgreSQL is required.
- no external report or tool runtime is required.
- no diagnosis, prescription, or treatment-plan output is introduced.
- Device2 LoRA work is not merged into Device1 mainline.
- report audit schema remains `p1_f5_report_audit_v1`.

## Acceptance

P1-F6 passes only when:

- all configured commands exit with code 0.
- every P1-F0 through P1-F5 artifact exists and reports `status=ok`.
- every required P8 artifact exists and reports `status=ok`.
- P1-F4 reports zero failed commands and zero failed artifacts.
- P1-F5 reports audit schema `p1_f5_report_audit_v1`.
- secret scan reports `finding_count=0`.
- boundary summary marks the post-P8 route as authoritative and the older P1
  gate as non-authoritative.

When it passes, the recommended next slice is P2/P10 release hardening and
packaging.
