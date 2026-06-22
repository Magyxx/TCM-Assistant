# P4.6.6 Encoding / Chinese Literal Stability Report

Generated: 2026-06-20

This phase audited user-visible Chinese literals and stabilized the canonical
safety boundary text without changing API schemas, report fields, SQLite schema,
risk-rule behavior, or RAG state boundaries.

## scanned_files

Scanned roots:

- `app/`
- `scripts/`
- `tests/`
- `docs/`
- `artifacts/`

Output-sensitive files reviewed in detail:

- `app/api/models.py`
- `app/safety/report_safety.py`
- `app/chains/report_chain.py`
- `app/chains/turn_extractor.py`
- `app/graphs/consultation_nodes.py`
- `app/rag/knowledge_base.txt`
- `scripts/validate_p1_api_contract.py`
- `scripts/run_p4_gate.py`
- `tests/test_p0_report_safety.py`
- `tests/test_p4_6_chinese_literal_stability.py`
- `docs/CODE_HEALTH_ENCODING_CHINESE_LITERAL_STABILITY_REPORT.md`
- `artifacts/code_health_encoding_chinese_literal_stability.json`
- historical gate artifacts containing captured stdout tails

Searches covered mojibake markers, replacement characters, safety boundary
phrases, diagnostic/prescription-like phrases, API safety disclaimers, report
safety metadata, RAG warning text, docs demo output, and Chinese fixtures.

## mojibake_findings

| Category | Finding | Action |
| --- | --- | --- |
| source script mojibake | `scripts/validate_p1_api_contract.py` contained mojibake request literals for `胃胀两天` samples. | Fixed as a low-risk encoding repair. |
| captured artifact stdout | Gate artifacts contain garbled Chinese in `stdout_tail`, including current `artifacts/code_health_gate_baseline.json` and historical `artifacts/p1_gate_result.json`, `artifacts/p2_gate_result.json`, `artifacts/p3_gate_result.json`, `artifacts/p3_5_rc_gate.json`. | Recorded only; acceptance artifacts were not hand-edited. |
| superseded P4.6.6 draft | `docs/CODE_HEALTH_ENCODING_CHINESE_LITERAL_STABILITY_REPORT.md` and `artifacts/code_health_encoding_chinese_literal_stability.json` retain the earlier anchor wording. | Kept as historical draft artifacts; this report and `artifacts/chinese_literal_stability.json` are canonical for P4.6.6. |
| terminal display | PowerShell `Get-Content` without explicit UTF-8 rendering can display readable UTF-8 files as garbled text. | Recorded as environment/display caution, not file-content evidence. |

## safe_fixes_applied

- Standardized `SAFETY_BOUNDARY_TEXT` in `app/safety/report_safety.py`.
- Standardized `SAFETY_BOUNDARY_TEXT` in `app/chains/report_chain.py`.
- Repaired three mojibake validation inputs in `scripts/validate_p1_api_contract.py` to `胃胀两天` / `胃胀两天，没有其他症状，也没有胸痛`.
- Updated report-safety tests to assert the canonical safety boundary exactly.
- Added P4.6.6 golden tests for canonical safety constants, UTF-8 sensitive
  files, known mojibake markers, and runtime safety metadata.

Canonical safety boundary:

> 本系统仅用于问诊信息整理和风险提示，不构成诊断或治疗建议，不能替代医生判断。如出现持续高热、胸痛、呼吸困难、便血、意识异常、剧烈腹痛等高风险信号，应及时线下就医。

## changed_files

| File | Change | Risk |
| --- | --- | --- |
| `app/safety/report_safety.py` | Normalized `SAFETY_BOUNDARY_TEXT` to the canonical safety boundary. | low |
| `app/chains/report_chain.py` | Normalized duplicated `SAFETY_BOUNDARY_TEXT` to the canonical safety boundary. | low |
| `scripts/validate_p1_api_contract.py` | Repaired mojibake request literals in P1 contract validation samples. | low |
| `tests/test_p0_report_safety.py` | Updated safety golden assertions for the canonical boundary. | low |
| `tests/test_p4_6_chinese_literal_stability.py` | Added UTF-8, mojibake-marker, AST constant, and runtime metadata golden checks. | low |
| `docs/CHINESE_LITERAL_STABILITY_REPORT.md` | Added this P4.6.6 report. | low |
| `artifacts/chinese_literal_stability.json` | Added machine-readable P4.6.6 artifact. | low |
| `artifacts/code_health_gate_baseline.json` | Refreshed by `python scripts/run_code_health_gate.py`. | generated |
| `artifacts/p4_gate_result.json` | Refreshed by `python scripts/run_p4_gate.py`. | generated |

## golden_tests_added_or_updated

- `tests/test_p0_report_safety.py`
  - Checks the exact canonical `SAFETY_BOUNDARY_TEXT`.
  - Preserves existing checks that forbidden diagnosis/prescription phrases are
    sanitized without deleting structured `FinalReport` fields.
- `tests/test_p4_6_chinese_literal_stability.py`
  - Verifies selected output-sensitive files remain UTF-8 readable.
  - Uses AST parsing to assert source constants resolve to the canonical safety
    boundary even when split across adjacent Python string literals.
  - Verifies API `SAFETY_DISCLAIMER`, report safety `SAFETY_BOUNDARY_TEXT`, and
    runtime `FinalReport.metadata["safety_boundary"]` match exactly.
  - Checks selected files do not contain known mojibake markers.

## unchanged_medical_semantics

- API response schema unchanged; only safety text value is normalized.
- `TurnOutput`, `RunState`, and `FinalReport` fields and semantics unchanged.
- SQLite schema unchanged.
- Risk rules and risk-rule IDs unchanged.
- Safety meaning unchanged: the system remains limited to consultation
  information organization, risk reminders, and structured summaries.
- No diagnosis, prescription, treatment plan, or new medical judgment was added.
- RAG remains evidence/support only and does not rewrite core consultation state.

## unchanged_contracts

- `TurnOutput`, `RunState`, and `FinalReport` fields and semantics unchanged.
- FastAPI API contract unchanged.
- SQLite schema unchanged.
- Risk rule semantics unchanged.
- Legacy, gate, SFT, and RAG compatibility entrypoints kept.
- Fake/test path and real runtime path remain separated.
- RAG remains read-only with respect to core consultation state.
- Runtime `requirements.txt` unchanged.

## risky_items_not_touched

- Gate artifact `stdout_tail` mojibake was not manually rewritten.
- Old P4.6.6 draft report/artifact names were not deleted or rewritten.
- Prompt wording outside the canonical safety boundary was not globally edited.
- RAG knowledge-base lines were not normalized beyond scan and golden anchors.
- Docs containing product positioning history were not rewritten.
- Fake/test and real runtime paths were not mixed.

## known_cautions

- Soft code-health checks remain caution-only and separate from hard gates.
- Current and historical gate artifacts may still contain captured stdout mojibake.
- Old P4.6.6 draft report/artifact are retained for history and superseded by
  this canonical report.
- Some PowerShell display paths can render UTF-8 content incorrectly unless
  read with explicit UTF-8 handling.
- The safety boundary text value changed to the user-specified canonical text,
  while field/schema semantics and medical scope remain unchanged.

## validation_results

| Command | Status | Notes |
| --- | --- | --- |
| `python scripts/run_code_health_gate.py` | pass | hard=`ok`, soft=`caution`, hard checks 4/4. |
| `python scripts/run_p4_gate.py` | pass | Existing Transformers/PyTorch version warning remains advisory. |
| `python -m unittest discover -s tests` | pass | 273 tests passed. |
| `python -m compileall -q app scripts tests` | pass | Compile check passed. |
| `python -m json.tool artifacts/chinese_literal_stability.json` | pass | Final JSON syntax check passed. |

Targeted pre-validation:

- `python -m unittest tests.test_p0_report_safety tests.test_p4_6_chinese_literal_stability` passed: 10 tests.

## next_recommended_phase

P4.6.7 Phase 4 Freeze Report:

- Summarize P4.6.0 through P4.6.6.
- Record final contract and boundary freeze status.
- Confirm readiness for real-path validation without expanding medical scope.
