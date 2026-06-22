# Device 2 Onboarding

This document lets Device 2 start from a blank workstation and a blank Codex
thread after Device 1 publishes the P7 freeze baseline to GitHub.

## Baseline

- Project: TCM-Assistant
- Repository: `https://github.com/Magyxx/TCM-Assistant.git`
- Stable line after upload: `main`
- Exact P7 caution freeze tag: `v0.7.0-p7-caution`
- Device 2 work branch: `exp/sft-lora-extractor`
- P7 status: `caution`
- Sole P7 caution: Docker CLI was unavailable on Device 1

The exact P7 freeze commit is preserved by tag. The Device 2 branch starts from
the published P7 baseline and is an independent place for future SFT/LoRA
extractor preparation.

## Safety Boundary

TCM-Assistant is a structured traditional Chinese medicine inquiry assistant.
It is not an automatic diagnosis system, does not replace clinicians, and does
not prescribe treatment.

Hard rules:

- do not diagnose
- do not prescribe formulas, medication, dosage, or treatment plans
- do not replace offline medical evaluation
- surface high-risk signals as offline-care guidance
- never let RAG evidence overwrite core state fields such as
  `chief_complaint`, `duration`, or `risk_status`
- keep LoRA as a future optional single-turn structured extractor only
- never let LoRA directly write `risk_status`
- validate LLM output with Pydantic schemas and merge through deterministic
  rules
- preserve the frozen `/sessions`, `/turn`, `/state`, and `/report` response
  bodies
- carry P7 trace/status/evidence through metadata, additive endpoints,
  persisted queries, or artifacts
- never upload `.env`, local SQLite files, real patient data, model weights,
  adapters, checkpoints, runs, wandb, mlruns, or caches

## Clone And Branch

```bash
git clone https://github.com/Magyxx/TCM-Assistant.git
cd TCM-Assistant
git fetch --all --tags
git checkout exp/sft-lora-extractor
git status --short
```

Confirm:

```bash
git tag --list
git log --oneline --decorate -5
```

`v0.7.0-p7-caution` should point at the exact P7 freeze.

## Python Environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
```

If GPU or PyTorch installation needs a machine-specific wheel, follow the
official PyTorch selector for Device 2 and keep that decision local to the
environment. Do not commit environment-specific lockfiles unless requested.

## Environment File

```powershell
Copy-Item .env.example .env
```

Keep local validation in fake LLM mode unless real-LLM testing is explicitly
approved:

```text
TCM_ALLOW_REAL_LLM=false
TCM_LLM_MODE=fake
```

If a real API key is needed later, put it only in `.env` or the shell
environment. Never commit secrets.

## Validation

Run the non-Docker baseline:

```bash
python -m compileall -q app scripts tests
python -m unittest discover -s tests
python scripts/run_p7_gate.py
python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json
```

Expected Device 1 baseline:

- compileall: passed
- unittest: 333 tests passed
- P7 gate: `caution` if Docker CLI is unavailable
- secret scan: `status=ok`

On a Docker-capable Device 2, rerun:

```bash
python scripts/run_p7_gate.py
```

If Docker is available and the smoke path passes, the gate can move from
Docker-only `caution` toward `ok`. Do not retag a release without an explicit
release instruction.

## Local API

```bash
uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

The frozen compatibility surface includes:

- `/sessions`
- `/turn`
- `/state`
- `/report`

Do not add P7/P8 fields to those top-level response bodies.

## SFT/LoRA Branch Scope

Allowed preparation work:

- inspect the existing SFT data design and scripts
- prepare extractor contracts
- prepare redacted or synthetic dataset checks
- prepare offline evaluation harnesses
- document LoRA runtime boundaries

Out of scope until explicitly requested:

- real LoRA training
- committing adapters, checkpoints, model weights, or training outputs
- replacing deterministic risk rules
- writing `risk_status` from model output
- broad P8 agentic workflow development

Relevant starting points:

- `docs/sft_data_design.md`
- `docs/sft_training_plan.md`
- `scripts/build_sft_dataset.py`
- `scripts/train_sft_lora.py`
- `scripts/test_sft_lora_infer.py`
- `app/chains/sft_infer_chain.py`
- `app/schemas/sft_schemas.py`

## Before Pushing From Device 2

```bash
git status --short
git diff --check
python -m compileall -q app scripts tests
python -m unittest discover -s tests
python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json
```

Review every staged file. Keep `.env`, local databases, private data, weights,
adapters, checkpoints, generated runs, and caches out of git.
