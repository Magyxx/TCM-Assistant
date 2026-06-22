# P3 Final Release Candidate

Generated: 2026-06-19

## Goal

P3.5 defines the final local release-candidate gate for the P3 line. It is a
gate and documentation layer only. It does not add business behavior, public API
response fields, SQLite tables, a Web UI, auth, users, ORM, MemoryManager,
embeddings, Tool Registry, multi-agent behavior, diagnosis output, prescription
output, or treatment-plan output.

## Frozen Contract Baseline

- API version: `v1`
- API contract status: `frozen`
- API stage constant: `P3.4`
- RC gate phase: `P3.5`
- Recommended next phase on success: `P4.0`
- Public endpoint count: 6

The public endpoint set is:

- `GET /health`
- `GET /version`
- `POST /sessions`
- `POST /sessions/{session_id}/turn`
- `GET /sessions/{session_id}/state`
- `GET /sessions/{session_id}/report`

P3.5 does not change response body schemas. The P3.4 additions remain additive:
`X-API-Version: v1` and `GET /version`.

## RC Gate Command

Run the full P3.5 gate from the project root:

```bash
python scripts/run_p3_gate.py --json
```

The command writes two equivalent artifacts by default:

- `artifacts/p3_gate_result.json`
- `artifacts/p3_5_rc_gate.json`

For a fast artifact-only smoke check, use:

```bash
python scripts/run_p3_gate.py --summary-only --json
```

`--summary-only` is intended for script tests and quick inspection. The final RC
decision should use the full command without `--summary-only`.

## Checks Aggregated By P3.5

The full gate executes:

- P1 gate
- P2 gate through `scripts/run_p2_gate.py`
- P3.1 runtime config check
- P3.2 observability check
- P3.3 release packaging check
- P3.4 API contract check
- case corpus evaluation
- long-session reliability
- secret scan
- `git diff --check`
- `python -m unittest discover -s tests -p "test*.py"`

## Required Output Fields

The P3.5 artifact includes at least:

- `status`
- `stage`
- `current_gate_phase`
- `recommend_next`
- `checks_passed`
- `api_version`
- `api_contract_status`
- `breaking_change_detected`
- `diagnosis_system`
- `boundary_violations`
- `p1_gate`
- `p2_gate`
- `runtime_config`
- `observability`
- `release_packaging`
- `api_contract`
- `case_corpus`
- `long_session`
- `secret_scan`

## Acceptance Rules

The RC gate passes only when:

- `status=ok`
- `current_gate_phase=P3.5`
- `recommend_next=P4.0`
- `api_version=v1`
- `api_contract_status=frozen`
- `breaking_change_detected=false`
- `diagnosis_system=false`
- `boundary_violations=[]`
- P1/P2 contract is unchanged
- API response body schema is unchanged
- SQLite schema is unchanged
- unit tests pass
- secret scan passes
- `git diff --check` exits 0, allowing only existing Windows LF/CRLF warnings

## Release Boundary

This RC is still a local engineering release candidate. It is not production
medical software, not a diagnostic system, not a prescription system, and not a
treatment planning system. It remains an intake, state tracking, safety boundary,
and reproducibility validation prototype.
