# P11-POSTMERGE-SEAL

Post-Merge Main Seal after P11 Autopilot.

## Main Baseline

- Branch: `main`
- Validated main HEAD: `fe7386a40d1bb288f0da33feb9d1b50a62e4aacc`
- Validated origin/main HEAD: `fe7386a40d1bb288f0da33feb9d1b50a62e4aacc`
- P11 branch HEAD: `fffb52aec9dac803abeb8301ebcbdae39094f2ad`
- P11 base main before merge: `2338dcaca7f1f1b27ab19c9fdb4265ca649b4382`
- P11 branch head contained in main: yes
- Merge method: GitHub PR merge commit
- Merge commit: `fe7386a40d1bb288f0da33feb9d1b50a62e4aacc`
- PR: `https://github.com/Magyxx/TCM-Assistant/pull/3`

The merge commit parents are:

- `2338dcaca7f1f1b27ab19c9fdb4265ca649b4382`
- `fffb52aec9dac803abeb8301ebcbdae39094f2ad`

## P11 Milestone Commits

- M2 extractor adapter contract: `7edf2c48f0f168d37f117fcdc66abb7bf2100d9c`
- M3 workflow main path contract: `8ecb0dc51142018fc7205201ffe6421e521e0777`
- M4 RAG evidence contract: `91b7bf93dc8a8407f47be3ffcf250d14d4bb92a6`
- M5 FinalReport safety contract: `d4904125d84b9c46221892b643efa6f3f9e06a55`
- M6 regression suite: `4b770200f43c8a2399ed84a23ffcc9cbf8e8bc77`
- MG merge gate: `fffb52aec9dac803abeb8301ebcbdae39094f2ad`

## Validation Summary

- `python -m compileall -q app scripts tests`: passed
- `python -m unittest discover -s tests`: passed, 487 tests, skipped 1
- `python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json`: passed, finding_count 0
- `python scripts/verify_device2_local_lora_port.py --json --output reports/device2/local_lora_port_verification.json`: passed
- `python scripts/check_release_packaging.py`: passed, 12/12 checks
- `python scripts/verify_p11_post_lora_contract.py --json --output artifacts/p11/post_lora_runtime_contract.json`: ok
- `python scripts/verify_p11_extractor_adapter.py --json --output artifacts/p11/extractor_adapter_contract.json`: ok
- `python scripts/verify_p11_workflow_path.py --json --output artifacts/p11/workflow_path_contract.json`: ok
- `python scripts/verify_p11_rag_evidence_contract.py --json --output artifacts/p11/rag_evidence_contract.json`: ok
- `python scripts/verify_p11_report_safety_contract.py --json --output artifacts/p11/report_safety_contract.json`: ok
- `python scripts/verify_p11_regression_suite.py --json --output artifacts/p11/p11_regression_suite.json`: ok

## P11 Artifact Status

- `artifacts/p11/post_lora_runtime_contract.json`: ok
- `artifacts/p11/extractor_adapter_contract.json`: ok
- `artifacts/p11/workflow_path_contract.json`: ok
- `artifacts/p11/rag_evidence_contract.json`: ok
- `artifacts/p11/report_safety_contract.json`: ok
- `artifacts/p11/p11_regression_suite.json`: ok
- `artifacts/p11/p11_merge_gate.json`: ok
- `artifacts/p11/p11_postmerge_seal.json`: created by this seal

## Safety Boundary Status

- No diagnosis: preserved
- No prescription: preserved
- No replacement of clinician judgment: preserved
- `local_lora` / `local_vllm` cannot become final risk authority: preserved
- Extractor outputs must pass schema guard: preserved
- RAG evidence cannot overwrite core consultation state: preserved
- Optional live backends have explicit skip reasons: preserved

## Live vLLM Smoke

- Status: skipped
- Reason: `RUN_LOCAL_VLLM_SMOKE is not enabled`

## Tag Protection

- Tag: `v0.10.0-rc3`
- Tag object type: `tag`
- Tag object: `896e60e6509041b9d89d7d14d13ed6167a9447bd`
- Peeled commit: `5c404f245172736bdb5b8ad515a3fbbcb9251c12`
- Unchanged: yes

## Sensitive Files Check

The PowerShell tracked-file scan produced no matches for exact `.env`, model weight, adapter, or checkpoint patterns.

- Tracked model weights/checkpoints: none
- Tracked exact `.env`: none
- Secret scan finding_count: 0

## Artifact Housekeeping

Validation refreshed older stage artifacts and runtime logs. Those changes were reviewed as artifact churn and restored before creating this seal.

- Restored: existing P10, P11, P3, P6, P9, secret scan, knowledge index/eval, and Device2 verification artifacts refreshed by validation
- Kept: no pre-existing artifact churn
- Newly created: `docs/P11_POSTMERGE_SEAL.md`, `artifacts/p11/p11_postmerge_seal.json`

## Final Status

- Worktree after housekeeping and before seal files: clean
- Seal status: ok
- Next stage: P12 Service Readiness / FastAPI Persistence
