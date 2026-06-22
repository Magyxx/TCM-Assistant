# P4.6.3 Soft Tool Adoption Report

Generated/refreshed: 2026-06-20

This phase installs the development-only tools listed in `requirements-dev.txt`
and records a real soft-check baseline. Hard gate behavior remains separated
from soft reports: historical lint/type/dependency findings are recorded as
`caution` and do not fail the code-health gate.

## Installed Tools

| Tool | Version | Source | Runtime dependency |
| --- | --- | --- | --- |
| ruff | 0.15.18 | `requirements-dev.txt` | no |
| mypy | 2.1.0 | `requirements-dev.txt` | no |
| vulture | 2.16 | `requirements-dev.txt` | no |
| radon | 6.0.1 | `requirements-dev.txt` | no |
| deptry | 0.25.1 | `requirements-dev.txt` | no |
| pytest | 9.1.1 | `requirements-dev.txt` | no |

No dev-only tool was added to `requirements.txt`.

## Hard Gate Status

Status: ok

`python scripts/run_code_health_gate.py` completed successfully and kept hard
gate behavior separated from soft-tool cautions.

| Check | Status | Notes |
| --- | --- | --- |
| `python -m compileall -q app scripts tests` | ok | Compile check passed. |
| `python scripts/run_p4_gate.py` | ok | Existing transformers/PyTorch warning remains advisory. |
| `python -m unittest discover -s tests` | ok | 270 tests passed. |
| `python -m json.tool artifacts/code_health_gate_baseline.json` | ok | Gate artifact is valid JSON. |

## Soft Check Results

Status: caution

| Tool | Command | Result | Classification |
| --- | --- | --- | --- |
| ruff | `ruff check app scripts tests` | caution, 67 findings: F401=1, E402=63, F841=3 | caution |
| ruff format | `ruff format --check app scripts tests` | caution, 111 files would be reformatted; 24 files already formatted | caution |
| mypy | `mypy app scripts --ignore-missing-imports` | caution, duplicate module mapping for `scripts/audit_session.py` | caution |
| vulture | `vulture app scripts tests --min-confidence 80` | caution, 5 candidates | caution |
| radon | `radon cc app scripts -s -a` | ok, 657 blocks, average A | caution advisory |
| deptry | `deptry .` | caution, 6 dependency findings | caution |

## Safe Fixes Applied

| File | Rule | Risk | Change |
| --- | --- | --- | --- |
| `scripts/filter_sft_manual_only.py` | ruff F541 | safe | Removed a redundant `f` prefix from a print literal without changing emitted text. |

One apparent ruff F401 candidate was intentionally reverted:

| File | Rule | Risk | Reason |
| --- | --- | --- | --- |
| `app/api/sqlite_store.py` | ruff F401 | caution | `DEFAULT_DB_PATH` is imported by `scripts/run_case_corpus_eval.py` as a compatibility entrypoint. Removing it broke unittest, so it is kept with reason. |

## Findings By Category

### safe_fix_now

- `scripts/filter_sft_manual_only.py` F541: fixed.

### keep_with_reason

- `app/api/sqlite_store.py` F401: keep `DEFAULT_DB_PATH` compatibility re-export.
- E402 findings in executable scripts: keep for now because most are caused by
  path/bootstrap ordering needed for direct CLI execution.

### caution_review_later

- ruff format: 111-file formatting change is too broad for this phase.
- mypy: package-base configuration is needed before meaningful type checking.
- vulture: reported variables may be semantic placeholders or test fake
  signatures.
- radon: high-complexity functions remain advisory; splitting is out of scope.
- deptry: dependency findings touch runtime, SFT, and RAG compatibility.

### risky_do_not_touch

- `TurnOutput`, `RunState`, `FinalReport`.
- FastAPI response schema and API contract.
- SQLite schema.
- Risk rule semantics.
- legacy, gate, SFT, and RAG compatibility entrypoints.
- User-visible Chinese literals/mojibake.
- Runtime `requirements.txt`.

## Unchanged Contracts

- No API response schema changes.
- No SQLite schema changes.
- No risk rule semantic changes.
- No `TurnOutput`, `RunState`, or `FinalReport` semantic changes.
- No deletion of legacy/gate/SFT/RAG compatibility entrypoints.
- No high-complexity function split.
- This P4.6.3 soft-tool pass introduced no duplicate helper merge.
- No broad `ruff --fix` or `ruff format`.

## Known Cautions

- Soft tools are installed in the active development environment only.
- `ruff check` remains non-zero because historical findings are still present.
- `mypy` currently stops before full checking because of duplicate module
  discovery.
- `deptry` findings require human review before changing dependencies.
- P4 gate still emits the existing transformers/PyTorch version warning.
- Captured test output may contain existing mojibake.

## Artifacts

- Machine-readable soft baseline: `artifacts/code_health_soft_tools.json`
- Gate baseline refreshed by validation: `artifacts/code_health_gate_baseline.json`

## changed_files

| File | Change | Risk |
| --- | --- | --- |
| `scripts/filter_sft_manual_only.py` | Removed one redundant `f` prefix from a print literal. | safe |
| `docs/CODE_HEALTH_SOFT_TOOL_REPORT.md` | Added P4.6.3 soft-tool adoption report. | safe |
| `artifacts/code_health_soft_tools.json` | Added machine-readable P4.6.3 soft-tool baseline. | safe |
| `artifacts/code_health_gate_baseline.json` | Refreshed by `python scripts/run_code_health_gate.py`. | generated |
| `artifacts/p4_gate_result.json` | Refreshed by P4 gate validation. | generated |
| `artifacts/p4_5_gate.json` | Refreshed by P4 gate validation. | generated |

## validation_results

| Command | Status | Notes |
| --- | --- | --- |
| `python scripts/run_code_health_gate.py` | pass | hard=`ok`, soft=`caution`, 4/4 hard checks passed. |
| `python scripts/run_p4_gate.py` | pass | Existing Transformers/PyTorch warning remains advisory. |
| `python -m unittest discover -s tests` | pass | 270 tests passed. |
| `python -m compileall -q app scripts tests` | pass | Compile check passed. |
| `python -m json.tool artifacts/code_health_soft_tools.json` | pass | P4.6.3 JSON artifact is valid. |

## Next Recommended Phase

P4.6.4 Structural Cleanup.

Recommended scope:

- Decide whether script bootstrap E402 findings should be kept, moved, or
  configured with focused ignores.
- Add reviewed mypy configuration instead of changing runtime code to satisfy
  package discovery.
- Review deptry findings against real runtime/SFT/RAG compatibility before
  changing dependencies.
- Treat repository-wide formatting as a separate, explicit phase if desired.

## risky_items_not_touched

- `TurnOutput`, `RunState`, and `FinalReport` fields and semantics.
- FastAPI API contract and response body semantics.
- SQLite schema and historical session compatibility.
- Risk rule semantics.
- Legacy, gate, SFT, and RAG compatibility entrypoints.
- Runtime `requirements.txt`.
- User-visible Chinese literals and existing mojibake candidates.

## next_recommended_phase

P4.6.4 Structural Cleanup:

- Prefer narrowly scoped shared helpers over broad formatting or mass refactors.
- Keep all runtime contracts, compatibility entrypoints, and risk semantics frozen.
- Validate any structural change through code-health gate, P4 gate, unittest, and compileall.
