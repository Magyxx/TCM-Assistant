# P4.6.6 Encoding / Chinese Literal Stability Report

Generated: 2026-06-20

This phase freezes output-sensitive Chinese safety literals with focused tests.
It does not rewrite Chinese copy, repair suspected mojibake globally, or change
runtime behavior. The goal is stability: future edits should fail fast if core
safety wording is accidentally removed or unreadable as UTF-8.

## Stability Anchors

| File | Required phrases |
| --- | --- |
| `app/api/models.py` | `本系统仅用于问诊信息整理和风险提示`; `不构成诊断或治疗建议`; `不能替代医生判断` |
| `app/chains/report_chain.py` | `本系统不是诊断系统`; `仅用于问诊信息整理`; `不能替代医生判断` |
| `app/chains/turn_extractor.py` | `你不能诊断`; `你不能开方`; `不能输出药物、处方或替代医生判断的内容` |
| `app/rag/knowledge_base.txt` | `本系统输出仅用于问诊辅助整理`; `不构成诊断意见`; `不能替代线下医生面诊` |

## Repair Policy

- No broad text conversion in P4.
- No user-visible wording rewrite without product copy review.
- No API snapshot change unless separately approved.
- Terminal mojibake is treated separately from file-content UTF-8 validity.
- Suspected file-content mojibake must be handled in a future reviewed phase
  with before/after snapshots.

## changed_files

| File | Change | Risk |
| --- | --- | --- |
| `tests/test_p4_6_chinese_literal_stability.py` | Added UTF-8 and required-phrase checks for output-sensitive Chinese safety literals. | safe |
| `docs/CODE_HEALTH_ENCODING_CHINESE_LITERAL_STABILITY_REPORT.md` | Added this P4.6.6 report. | safe |
| `artifacts/code_health_encoding_chinese_literal_stability.json` | Added machine-readable P4.6.6 artifact. | safe |

## validation_results

| Command | Status | Notes |
| --- | --- | --- |
| `python scripts/run_code_health_gate.py` | pass | hard=`ok`, soft=`caution`, 4/4 hard checks passed. |
| `python scripts/run_p4_gate.py` | pass | Existing Transformers/PyTorch warning remains advisory. |
| `python -m unittest discover -s tests` | pass | 270 tests passed. |
| `python -m compileall -q app scripts tests` | pass | Compile check passed. |
| `python -m json.tool artifacts/code_health_encoding_chinese_literal_stability.json` | pass | P4.6.6 JSON artifact is valid. |

## unchanged_contracts

- `TurnOutput`, `RunState`, and `FinalReport` fields and semantics unchanged.
- FastAPI API contract unchanged.
- SQLite schema unchanged.
- Risk rule semantics unchanged.
- Legacy, gate, SFT, and RAG compatibility entrypoints kept.
- Fake/test path and real runtime path remain separated.
- RAG remains read-only with respect to core consultation state.
- Runtime `requirements.txt` unchanged.
- No Chinese safety copy was rewritten.

## known_cautions

- This phase freezes selected high-value anchors; it is not a complete copy
  review of every Chinese literal in the repository.
- Existing terminal output may still render garbled depending on PowerShell
  encoding settings even when source files are UTF-8.
- Future literal repair needs API/report snapshots and human copy approval.
- The bundled knowledge base remains a tiny smoke-test corpus, not a real
  medical textbook or guideline import.

## risky_items_not_touched

- User-visible API schema and response fields.
- Report generation semantics.
- Risk rules and safety post-check behavior.
- RAG retrieval ranking and evidence-pack semantics.
- Existing knowledge-base content beyond stability anchors.
- Suspected mojibake candidates outside this focused anchor list.

## next_recommended_phase

P4.6.7 Phase 4 Freeze Report:

- Summarize P4.6.0-P4.6.6 results.
- Confirm contracts and risky items remain frozen.
- Record final gate status and readiness for real-path validation.
