# P11-MG Merge Gate Report

## Scope

- Stage: P11-MG Merge Gate
- Branch: `p11/autopilot-mainline-hardening`
- HEAD: `4b770200f43c8a2399ed84a23ffcc9cbf8e8bc77`
- Origin branch HEAD: `4b770200f43c8a2399ed84a23ffcc9cbf8e8bc77`
- Base main: `2338dcaca7f1f1b27ab19c9fdb4265ca649b4382`
- PR URL: <https://github.com/Magyxx/TCM-Assistant/pull/new/p11/autopilot-mainline-hardening>

## P11 Commit Stack

| Milestone | Commit | Result |
| --- | --- | --- |
| P11-M2 extractor adapter contract | `7edf2c48f0f168d37f117fcdc66abb7bf2100d9c` | ok |
| P11-M3 workflow main path contract | `8ecb0dc51142018fc7205201ffe6421e521e0777` | ok |
| P11-M4 RAG evidence contract | `91b7bf93dc8a8407f47be3ffcf250d14d4bb92a6` | ok |
| P11-M5 FinalReport safety contract | `d4904125d84b9c46221892b643efa6f3f9e06a55` | ok |
| P11-M6 regression suite | `4b770200f43c8a2399ed84a23ffcc9cbf8e8bc77` | ok |

## Diff Summary

- Compared range: `origin/main...HEAD`
- Shortstat: `49 files changed, 4946 insertions(+), 4 deletions(-)`
- Changed file categories:
  - docs: 8 files
  - app contract: 6 files
  - tests: 23 files
  - scripts: 6 files
  - artifacts: 6 files

Diff review found only P11 documentation, tests, verifier scripts, P11 artifacts, and necessary app contract changes. No model weights, adapter/checkpoint files, `.env`, training products, private path material, default live vLLM enablement, or unrelated large files were found.

## Contract Review

| Area | Result | Evidence |
| --- | --- | --- |
| Backend contract | ok | `verify_p11_post_lora_contract.py` and `verify_p11_extractor_adapter.py` passed. Optional live backends remain non-default and skip with explicit reasons. |
| Workflow path | ok | `verify_p11_workflow_path.py` passed. Schema validation, state update, risk rules, next action, and report readiness remain in the audited path. |
| RAG evidence | ok | `verify_p11_rag_evidence_contract.py` passed. Evidence may feed report/evidence fields but cannot overwrite core inquiry or risk state. |
| FinalReport safety | ok | `verify_p11_report_safety_contract.py` passed. Diagnosis and prescription claims are blocked or rewritten; high-risk triage and citations are preserved. |
| Regression suite | ok | `verify_p11_regression_suite.py` passed with 487 unit tests and 1 skipped test. |

## Validation

| Check | Result |
| --- | --- |
| `python -m compileall -q app scripts tests` | passed |
| `python -m unittest discover -s tests` | passed: 487 tests, skipped=1 |
| `python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json` | passed: finding_count=0 |
| `python scripts/verify_device2_local_lora_port.py --json --output reports/device2/local_lora_port_verification.json` | passed |
| `python scripts/check_release_packaging.py` | passed: 12/12 |
| P11 verifier scripts | passed: M1-M6 ok |

The direct unittest run printed `OK (skipped=1)`; the P11 regression-suite verifier reran unittest discovery and returned exit code 0.

## Safety Boundaries

- `local_lora` and `local_vllm` are not default hard dependencies.
- `local_lora` has no final risk authority; risk remains owned by the risk rules layer.
- RAG core overwrite guard remains enabled for chief complaint, duration, risk status, and risk rule identifiers.
- FinalReport safety keeps no-diagnosis and no-prescription boundaries.
- Live vLLM smoke status: skipped.
- Live vLLM smoke reason: `RUN_LOCAL_VLLM_SMOKE is not enabled`.

## Sensitive Files And Tag Protection

- Tracked model weights/checkpoints/adapters: none.
- Tracked exact `.env`: none.
- Secret scan finding count: 0.
- Protected tag: `v0.10.0-rc3`
- Tag object type: `tag`
- Tag object SHA: `896e60e6509041b9d89d7d14d13ed6167a9447bd`
- Peeled commit SHA: `5c404f245172736bdb5b8ad515a3fbbcb9251c12`
- Tag unchanged: yes.

## Merge Recommendation

- ready_for_pr_merge: yes
- Recommended merge method: GitHub PR merge commit
- Next stage after merge: P11-POSTMERGE-SEAL, then P12 Service Readiness / FastAPI Persistence

