# P4.6.4 Structural Cleanup Report

Generated: 2026-06-20

This phase performs one narrow structural cleanup: gate JSON redaction now uses
a shared helper instead of three duplicate private functions. It does not change
runtime business behavior, public API models, persistence schema, risk rules, or
compatibility entrypoints.

## changed_files

| File | Change | Risk |
| --- | --- | --- |
| `scripts/gate_utils.py` | Added shared `redact_preserving_schema` helper for gate artifact redaction. | safe |
| `scripts/run_p2_gate.py` | Replaced duplicate private redaction helper with shared import. | safe |
| `scripts/run_p3_gate.py` | Replaced duplicate private redaction helper with shared import. | safe |
| `scripts/run_p4_gate.py` | Replaced duplicate private redaction helper with shared import. | safe |
| `tests/test_p4_6_gate_utils.py` | Added focused unit test for recursive gate payload redaction. | safe |
| `docs/CODE_HEALTH_STRUCTURAL_CLEANUP_REPORT.md` | Added this P4.6.4 report. | safe |
| `artifacts/code_health_structural_cleanup.json` | Added machine-readable P4.6.4 artifact. | safe |

## validation_results

| Command | Status | Notes |
| --- | --- | --- |
| `python scripts/run_code_health_gate.py` | pass | hard=`ok`, soft=`caution`, 4/4 hard checks passed. |
| `python scripts/run_p4_gate.py` | pass | Existing Transformers/PyTorch warning remains advisory. |
| `python -m unittest discover -s tests` | pass | 269 tests passed. |
| `python -m compileall -q app scripts tests` | pass | Compile check passed. |
| `python -m json.tool artifacts/code_health_structural_cleanup.json` | pass | P4.6.4 JSON artifact is valid. |

## unchanged_contracts

- `TurnOutput`, `RunState`, and `FinalReport` fields and semantics unchanged.
- FastAPI API contract unchanged.
- SQLite schema unchanged.
- Risk rule semantics unchanged.
- Legacy, gate, SFT, and RAG compatibility entrypoints kept.
- Runtime `requirements.txt` unchanged.
- Real runtime path and fake/test path remain separate.
- RAG remains read-only with respect to core问诊 state.

## known_cautions

- The shared helper intentionally preserves previous behavior, including tuple
  payloads being serialized as JSON-compatible lists.
- Historical soft-tool findings remain advisory and are not auto-fixed here.
- P4 gate may still emit the existing Transformers/PyTorch version warning.

## risky_items_not_touched

- Public Pydantic schema fields and meanings.
- FastAPI request/response contract.
- SQLite tables, columns, and schema metadata.
- Risk rule IDs, keyword semantics, and sticky high-risk behavior.
- Legacy MVP/stateful scripts, gate scripts, SFT scripts, and RAG compatibility
  modules.
- User-visible Chinese literals.

## next_recommended_phase

P4.6.5 Deprecation & Compatibility Plan:

- Inventory legacy, gate, SFT, and RAG compatibility entrypoints.
- Mark keep/deprecate candidates without deleting or moving them.
- Require human approval before any future removal.
