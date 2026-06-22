# P3 Gate Plan

Generated: 2026-06-18

## Purpose

P3.2 still does not implement a separate P3 gate runner. The current executable
acceptance path remains `scripts/run_p2_gate.py`, now with P3.1 runtime config
and P3.2 observability checks added to the inherited P1/P2 validation.

## Current P3.2 Gate Position

Current acceptance entrypoint:

```bash
python scripts/run_p2_gate.py --output artifacts/p2_gate_result.json
```

This command includes:

- `runtime_config_check`, which runs
  `python scripts/check_runtime_config.py --json --output artifacts/p3_1_runtime_config.json`
- `observability_check`, which runs
  `python scripts/check_observability.py --json --output artifacts/p3_2_observability.json`
- P1 gate
- unittest discovery
- case corpus eval
- long-session demo
- secret scan
- `git diff --check`

Supporting commands:

```bash
python scripts/run_p1_gate.py --output artifacts/p1_gate_result.json
python -m unittest discover -s tests
python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json
git diff --check
```

P3.2 does not add:

- `scripts/run_p3_gate.py`
- packaging checks
- API versioning checks
- RC bundle checks

## Future P3 Gate Shape

A future P3 gate should inherit the current gate checks:

- runtime config check
- observability check
- P1 gate
- unittest discovery
- case corpus eval
- long-session demo
- secret scan
- `git diff --check`

It may then add checks as the later phases land:

- P3.3 release manifest and reproducibility checks
- P3.4 API compatibility policy checks
- P3.5 release-candidate bundle checks

## Implementation Rule

Do not implement `scripts/run_p3_gate.py` until multiple P3 checks need their
own composition layer. A placeholder runner would create a false sense of
validation. P3.2 keeps the P2 gate as the source of executable acceptance and
records runtime config and observability checks in `artifacts/p3_1_runtime_config.json`
and `artifacts/p3_2_observability.json`.

## Boundary Requirements

Any future P3 gate must continue to verify:

- no diagnosis output
- no prescription output
- no treatment-plan output
- no committed real secrets
- no real LLM key as a default acceptance dependency
- no API success contract breakage
- `/health` remains exact P1.1 unless a separately approved compatibility plan
  changes that policy
