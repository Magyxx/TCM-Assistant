# Device 2 Codex Prompt

Paste this prompt into a fresh Codex thread on Device 2.

```text
You are now taking over TCM-Assistant on Device 2.

Repository:
https://github.com/Magyxx/TCM-Assistant.git

Local path on Device 2:
<fill in after clone>

Start by running:
git fetch --all --tags
git checkout exp/sft-lora-extractor
git status --short
git branch --show-current
git log --oneline --decorate -5
git tag --list

Project identity:
TCM-Assistant is a structured traditional Chinese medicine inquiry assistant.
It is not an automatic diagnosis system, does not replace clinicians, and does
not prescribe treatment. It converts natural-language symptom descriptions into
structured RunState fields, asks for missing inquiry details, tracks safety
signals, and produces structured reports with safety boundaries and evidence
references.

Current baseline:
- P7 freeze is complete for the non-Docker local baseline.
- Exact caution tag: v0.7.0-p7-caution.
- P7 status is caution only because Device 1 did not have Docker CLI.
- Non-Docker validation on Device 1 passed:
  python -m compileall -q app scripts tests
  python -m unittest discover -s tests
  python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json
- python scripts/run_p7_gate.py exited non-zero only because Docker smoke could
  not run on Device 1.

Hard safety boundaries:
1. Do not diagnose.
2. Do not prescribe medication, formulas, dosage, or treatment plans.
3. Do not replace doctors or offline medical evaluation.
4. High-risk signals must prompt offline medical care guidance.
5. RAG evidence may enrich explanation, advice, or impression, but must not
   overwrite chief_complaint, duration, risk_status, or other core state fields.
6. LoRA is only a future optional single-turn structured extractor.
7. LoRA must not directly write risk_status.
8. LLM output must be validated by Pydantic schema and merged through rules.
9. The frozen P1/P3 API contract must not be broken:
   /sessions
   /turn
   /state
   /report
10. P7 trace/status/evidence must live in metadata, additive endpoints,
    persistence queries, or artifacts, not in legacy top-level response bodies.
11. Do not upload real patient private data.
12. Do not upload .env.
13. Do not upload local SQLite/db runtime files.
14. Do not upload model weights, LoRA adapters, checkpoints, runs, wandb,
    mlruns, or cache directories.

This branch is the Device 2 entry for future SFT/LoRA extractor work:
exp/sft-lora-extractor

For this first Device 2 session, do not start P8 development and do not train
LoRA. First verify environment setup, read:
- README.md
- docs/DEVICE2_ONBOARDING.md
- docs/BRANCHING_POLICY.md
- docs/P7_RELEASE_FREEZE.md
- docs/API_CONTRACT_FREEZE.md
- docs/sft_data_design.md
- docs/sft_training_plan.md

Then install and validate:
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
Copy-Item .env.example .env
python -m compileall -q app scripts tests
python -m unittest discover -s tests
python scripts/run_p7_gate.py
python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json

If Docker exists on Device 2, use the P7 gate artifact to report whether Docker
smoke moves from caution to ok. Do not create a new release tag unless the user
explicitly asks.
```
