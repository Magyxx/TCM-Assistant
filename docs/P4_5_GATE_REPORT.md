# P4.5 Gate Report

Generated: 2026-06-20

## Summary

P4.5 adds a P4 regression and boundary gate.

Implemented:

- `scripts/run_p4_gate.py`
- `tests/test_p4_5_gate.py`
- `artifacts/p4_gate_result.json`
- `artifacts/p4_5_gate.json`

## Latest Result

`python scripts/run_p4_gate.py --json --output artifacts/p4_gate_result.json --rc-output artifacts/p4_5_gate.json`

Result:

- status: `ok`
- checks: `9/9`
- boundary violations: `[]`
- API response body changed: `false`
- SQLite schema changed: `false`
- diagnosis system: `false`

## Gate Checks

- P3.5 baseline artifact remains valid.
- API contract remains frozen.
- SQLite schema remains compatible.
- P4.1 workflow adapter boundary passes.
- P4.2 memory boundary passes.
- P4.3 RAG boundary passes.
- P4.4 tool registry boundary passes.
- Report safety boundary passes.
- P4 unit tests pass.

## Known Validation Scope

The P4 gate uses the existing P3.5 artifact as inherited baseline evidence. It does not rerun the full P3.5 long gate by default. The full inherited gate remains available through:

```bash
python scripts/run_p3_gate.py --json
```

## Release Boundary

P4 remains a controlled consultation workflow. It is still not diagnosis, not prescription, not treatment plan, and not doctor replacement.

