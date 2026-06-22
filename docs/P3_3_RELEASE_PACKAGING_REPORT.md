# P3.3 Release Packaging Report

Generated: 2026-06-18

## Added Files

- `scripts/check_release_packaging.py`
- `tests/test_p3_3_release_packaging.py`
- `tests/test_p3_3_release_packaging_script.py`
- `docs/RELEASE_PACKAGING.md`
- `docs/P3_3_RELEASE_PACKAGING_REPORT.md`
- `artifacts/p3_3_release_packaging.json`
- `artifacts/p3_3_release_packaging_check.json`

## Modified Files

- `.env.example`
- `scripts/run_p2_gate.py`
- `tests/test_p3_2_observability_script.py`
- `tests/test_p2_5_p2_gate_runner.py`

## Release Packaging Summary

P3.3 defines a local reproducible prototype / local engineering release
candidate. It centralizes local setup, runtime modes, validation commands,
manifest contents, docs boundaries, artifacts boundaries, and secret policy.

## Manifest Field Summary

`artifacts/p3_3_release_packaging.json` includes `phase`, `status`,
`project_name`, `release_type`, `runtime_modes`, `required_commands`, `docs`,
`scripts`, `artifacts`, `tests`, `env_files`, `secret_policy`,
`runtime_dirs`, `contract_changed`, `sqlite_schema_changed`,
`boundary_violated`, and `created_at`.

The manifest uses relative paths and does not include local absolute paths or
secret values.

## `.env.example` Summary

`.env.example` now documents P3.1/P3.2 runtime settings:

```env
TCM_RUNTIME_MODE=local
TCM_API_DB_PATH=.runtime/tcm_assistant.sqlite3
TCM_RUNTIME_DIR=.runtime
TCM_ARTIFACTS_DIR=artifacts
TCM_ALLOW_REAL_LLM=false
TCM_LOG_LEVEL=INFO
TCM_REDACT_LOGS=true
TCM_CONFIG_STRICT=false
OPENAI_API_KEY=
```

Real LLM use is disabled by default and `.env` remains local-only.

## Reproducibility Commands Summary

```bash
python scripts/check_runtime_config.py
python scripts/check_observability.py
python scripts/check_release_packaging.py
python scripts/run_p1_gate.py
python scripts/run_p2_gate.py
python scripts/run_case_corpus_eval.py
python scripts/run_long_session_demo.py
python scripts/secret_scan.py
python -m unittest discover -s tests -p "test*.py"
git diff --check
```

## `check_release_packaging.py` Output Summary

Final output:

```json
{
  "status": "ok",
  "phase": "P3.3",
  "checks_total": 12,
  "checks_passed": 12,
  "warnings": [],
  "errors": []
}
```

## `run_p2_gate.py` Integration Summary

`release_packaging_check` is integrated into `scripts/run_p2_gate.py`. The gate
now reports 9/9 checks when P3.1, P3.2, P3.3, P1, P2, secret scan, and diff
checks pass.

No separate `run_p3_gate.py` was added because the current project route keeps
P3 checks composed through `run_p2_gate.py` until a dedicated P3.5 RC gate is
defined.

## `p3_3_release_packaging.json` Summary

The manifest identifies P3.3 as a local reproducible package, not a production
release. It lists runtime modes, required commands, docs, scripts, artifacts,
tests, environment files, secret policy, runtime directories, non-goals, and
contract/schema boundary flags.

## Validation Results

- `python scripts/check_runtime_config.py`: ok, P3.1, 0 warnings, 0 errors
- `python scripts/check_observability.py`: ok, P3.2, 9 checks, structured logging and redaction enabled
- `python scripts/check_release_packaging.py`: ok, P3.3, 12/12 checks
- `python scripts/run_p1_gate.py`: ok, 13/13 checks
- `python scripts/run_p2_gate.py`: ok, current gate phase P3.3, 9/9 checks, recommends P3.4
- `python scripts/run_case_corpus_eval.py`: ok, 12/12 cases
- `python scripts/run_long_session_demo.py`: ok, 3 sessions x 50 turns, `secret_found=false`
- `python scripts/secret_scan.py`: ok, 0 findings, 15 allowlisted synthetic findings, 216 files scanned
- `python -m unittest discover -s tests -p "test*.py"`: ok, 235 tests
- `python -m unittest discover`: ok, 0 tests discovered; this is not treated as full discovery
- `git diff --check`: ok, exit code 0; Windows LF/CRLF warnings only

## Contract And Schema

- P1/P2 contract changed: no
- SQLite schema changed: no
- Boundary violated: no

## Known Limitations

P3.3 is a local release package layer. It does not provide production hosting,
API versioning, CI/CD, monitoring backends, installable packages, or a P3.5 RC
gate.

## Recommendation

Recommend entering P3.4 API versioning after preserving the current P1/P2
contract and SQLite schema snapshots.
