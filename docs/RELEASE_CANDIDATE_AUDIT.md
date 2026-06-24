# Release Candidate Audit And Commit Packaging

This is the final audit layer for the post-P8 Device1 mainline package.

It validates that the current worktree can be reviewed and packaged as a local
engineering release candidate. It does not create a git commit by itself.
Staging, committing, pushing, or opening a PR still requires explicit user
approval.

## Scope

The audit verifies:

- P2/P10 release hardening is ready.
- P1-F6 post-P8 productization remains ready.
- P10M2, P10M3, and P10-M4A artifacts remain accepted.
- release packaging and secret scan remain clean.
- focused RC tests pass.
- `git diff --check` passes.
- the pending worktree package contains code, scripts, tests, docs, and
  artifacts.
- no model weights, LoRA adapters, checkpoints, `.env`, or private patient data
  paths are part of the commit candidate.

## Command

```powershell
python scripts/verify_release_candidate_audit.py
```

Machine-readable output:

```powershell
python scripts/verify_release_candidate_audit.py --json --output artifacts/release_candidate_audit.json
```

For a slower broad regression run, add:

```powershell
python scripts/verify_release_candidate_audit.py --full-unittest
```

## Artifact

The audit writes:

- `artifacts/release_candidate_audit.json`

The artifact records command results, accepted artifacts, package inventory,
forbidden-path checks, branch, commit, and `release_candidate_ready`.

## Acceptance

The audit passes only when:

- all configured commands exit with code 0.
- P2/P10 release hardening reports `release_hardening_ready=true`.
- required downstream artifacts report `status=ok`.
- secret scan reports zero findings.
- the worktree package includes `app`, `scripts`, `tests`, `docs`, and
  `artifacts` groups.
- no forbidden model/adapter/checkpoint/private-data paths are present in the
  staged-or-candidate package.

## Boundary Statement

The package remains a local engineering release candidate, not a production
medical product. It does not diagnose, prescribe, plan treatment, merge Device2
LoRA training artifacts, or require a real LLM/local LoRA runtime.

Git commit, push, and PR creation are intentionally left as explicit user-owned
actions.
