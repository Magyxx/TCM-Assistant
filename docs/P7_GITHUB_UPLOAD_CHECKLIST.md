# P7 GitHub Upload Checklist

Use this checklist before pushing the P7 freeze baseline to GitHub.

## Required State

- [ ] `docs/P7_RELEASE_FREEZE.md` describes P7 status as functional complete
      with Docker-only caution.
- [ ] `docs/API_CONTRACT_FREEZE.md` documents the frozen legacy API contract.
- [ ] `docs/ARTIFACTS_POLICY.md` documents artifact retention and exclusions.
- [ ] `docs/BRANCHING_POLICY.md` documents P7, P7.5, P8, and SFT branch flow.
- [ ] README states that P7 is `caution` only because local Docker CLI is
      unavailable.
- [ ] `.gitignore` excludes secrets, local databases, model weights, adapters,
      checkpoints, training outputs, experiment trackers, caches, and private
      raw data.

## Validation Commands

Run:

```bash
python -m unittest discover -s tests
python -m compileall -q app scripts tests
python scripts/run_p7_gate.py
```

Expected on the current local machine:

- `unittest`: pass
- `compileall`: pass
- P7 gate: `caution` with Docker smoke pending

Confirm the gate caution is Docker-only:

- `artifacts/p7_docker_smoke.json` has `docker_runtime_available=false`
- `artifacts/p7_docker_smoke.json` has `docker_smoke_pass=false`
- `artifacts/p7_failure_analysis.json` has no non-Docker blocker
- `artifacts/p7_gate_report.json` has non-Docker metrics passing

## Files To Keep

Keep source code, tests, docs, configuration templates, Docker files, and key
JSON release artifacts.

Key artifacts:

- `artifacts/p7_gate_report.json`
- `artifacts/p7_docker_smoke.json`
- `artifacts/p7_failure_analysis.json`
- P7 validation JSON files referenced from `p7_gate_report.json`
- historical gate artifacts that document P1-P6 baseline evolution

## Files Not To Upload

Do not upload:

- `.env` or `.env.*`
- real patient private data
- raw private consultation logs
- local SQLite databases
- model weights
- LoRA adapters
- checkpoints
- generated training outputs
- `wandb` or `mlruns`
- local cache directories
- temporary artifacts under `artifacts/tmp/`

## Suggested Git Commands

Review first:

```bash
git status --short
git diff --check
```

Freeze commit:

```bash
git add .
git commit -m "freeze: P7 service storage memory tools observability gate"
git tag v0.7.0-p7-caution
```

After Docker smoke passes on a Docker-capable host:

```bash
python scripts/run_p7_gate.py
git tag v0.7.0-p7-ok
```
