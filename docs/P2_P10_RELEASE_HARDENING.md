# P2/P10 Release Hardening And Packaging

This stage follows P1-F6 and turns the post-P8 productization route into a
single release-hardening validation entry point.

It does not add new clinical behavior. It composes already-accepted foundations
and current P10 before-LoRA checks into one repeatable package gate.

## Scope

The gate verifies:

- P1-F6 post-P8 productization final acceptance.
- P10M2 core finalization before LoRA.
- P10M3 Device1 `local_lora` extractor backend boundary.
- P10-M4A extractor contract reconciliation.
- P3.3 local release packaging check.
- focused release regression tests.
- secret scan and `git diff --check`.

## Command

```powershell
python scripts/verify_p2_p10_release_hardening.py
```

Machine-readable output:

```powershell
python scripts/verify_p2_p10_release_hardening.py --json --output artifacts/p2_p10_release_hardening.json
```

For a slower broad regression run, add:

```powershell
python scripts/verify_p2_p10_release_hardening.py --full-unittest
```

## Artifact

The gate writes:

- `artifacts/p2_p10_release_hardening.json`

The artifact records command results, parsed artifact summaries, release
boundaries, failed commands, failed artifacts, branch, commit, and
`release_hardening_ready`.

## Acceptance

The gate passes only when:

- all configured commands exit with code 0.
- P1-F6 reports `post_p8_productization_ready=true`.
- P10M2 reports core, RAG, citation, safety, export, Docker file, failure-memory,
  P10M1, and P9M2 checks as passed.
- all P10M2 safety redteam counters are zero.
- P10M3 mock/local LoRA contract checks pass, and live smoke is either passed or
  cleanly skipped when no local service is running.
- P10-M4A extractor contract checks pass.
- no LoRA model weights, adapters, or checkpoints are committed.
- release packaging reports all checks passed and no boundary/contract/schema
  drift.
- secret scan reports zero findings.

## Boundary Statement

This remains a local engineering release candidate. It is not a production
medical product, diagnosis engine, prescription engine, treatment planner,
hospital deployment, or Device2 LoRA merge.

Real LLM and local LoRA runtimes remain optional and disabled or skipped unless
explicitly configured. SQLite and local artifacts remain the default release
shape.

When this gate passes, run the release candidate audit:

```powershell
python scripts/verify_release_candidate_audit.py --json --output artifacts/release_candidate_audit.json
```

If that audit passes, the package is ready for an explicit user-approved git
stage/commit/push workflow.
