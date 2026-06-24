# Clean Clone Verification

This guide verifies the sealed TCM-Assistant release candidate from a fresh
clone. It is intended for RC-S2 clean clone validation after the RC tag has
been pushed.

## Clone And Checkout

```powershell
git clone https://github.com/Magyxx/TCM-Assistant.git
cd TCM-Assistant
git checkout v0.10.0-rc1
```

If the sealed tag is `v0.10.0-rc2`, check out that tag instead:

```powershell
git checkout v0.10.0-rc2
```

## Install Dependencies

Use a clean Python environment, then install runtime and development
dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

## Verification Commands

```powershell
python -m compileall -q app scripts tests
python -m unittest discover -s tests
python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json
python scripts/verify_release_candidate_audit.py --json --output artifacts/release_candidate_audit.json
```

Optional retained validation commands:

```powershell
python scripts/verify_p1_foundation.py --json --output artifacts/p1_foundation_validation.json
python scripts/check_release_packaging.py --json --output artifacts/p3_3_release_packaging_check.json
python scripts/verify_clean_clone_reproducibility.py --json --output artifacts/clean_clone_reproducibility_validation.json
```

## Expected Results

- `compileall` exits with code 0.
- `unittest discover` exits with code 0.
- `secret_scan.py` reports `status=ok` with zero findings.
- `verify_release_candidate_audit.py` reports `status=ok`.
- `verify_release_candidate_audit.py` reports `release_candidate_ready=true`.
- `verify_clean_clone_reproducibility.py` reports `status=ok` when run.
- Downstream RC audit checks remain `ok`.

## RC-S2R Reproducibility Guard

`v0.10.0-rc2` includes two clean clone reproducibility repairs:

- P6 source registry hashing canonicalizes text line endings before comparing
  declared source hashes, so Windows CRLF checkout and LF checkout validate the
  same reviewed source content.
- report chain construction is lazy, so importing consultation graph modules in
  a clean environment does not require `OPENAI_API_KEY` or real LLM settings.

The dedicated guard command is:

```powershell
python scripts/verify_clean_clone_reproducibility.py --json --output artifacts/clean_clone_reproducibility_validation.json
```

## Runtime Boundary

Clean clone verification does not require:

- `OPENAI_API_KEY`
- local LoRA service availability
- embedding service availability
- vectorstore availability
- model weights
- LoRA adapters
- checkpoints

The release candidate validates the offline-safe source, test, documentation,
and audit artifact package only. It does not require Device2 training outputs or
external model caches.
