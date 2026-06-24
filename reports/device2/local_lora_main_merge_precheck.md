# D2-MP2 Device2 Local-LoRA Main Merge Precheck

Status: ok

Generated: 2026-06-24

## Summary

D2-MP2 verifies that `port/device2-local-lora-current-interface` can be cleanly merged into `origin/main` after the D2-MP1 port from the Device2 Local-LoRA branch to the current `ExtractorResult` interface.

- Branch: `port/device2-local-lora-current-interface`
- Validated port HEAD: `f6710195e3734f807f8e704cbed22aab3fcb1851`
- `origin/main` HEAD: `56f69eb2693fe3eecd4f1baf43603798d3b2aff9`
- Merge-base: `56f69eb2693fe3eecd4f1baf43603798d3b2aff9`
- Source Device2 branch: `origin/feature/device2-local-lora-extractor`
- Source Device2 HEAD: `8150e3cafec233f0afebcf4f67626b0a7224db21`
- Recommendation: enter D2-MP3 for push / PR creation / normal main merge flow.

`origin/main` did not move during this precheck. The merge-base matches the expected main base HEAD.

## D2-MP1 Commits

- `74e4b1e` docs: document device2 local lora main port plan
- `0518ab9` extractors: port local lora backend to current interface
- `0f738f8` tests: add local lora extractor schema and router guards
- `f671019` scripts: add device2 local lora port verification

## Diff Against origin/main

`git diff --name-status origin/main...HEAD`:

```text
M	.env.example
M	app/extractors/__init__.py
M	app/extractors/local_lora_extractor.py
M	app/extractors/openai_compatible_client.py
M	app/extractors/router.py
A	artifacts/device2_local_lora_port_validation.json
A	docs/DEVICE2_LOCAL_LORA_MAIN_PORT.md
A	docs/DEVICE2_VLLM_SERVING.md
A	reports/device2/local_lora_port_report.md
A	scripts/verify_device2_local_lora_port.py
M	tests/test_extractor_contract.py
M	tests/test_extractor_router.py
A	tests/test_local_lora_extractor.py
A	tests/test_local_lora_schema_guard.py
```

`git diff --check origin/main...HEAD`: passed.

## Merge Simulation

Temporary worktree:

```text
C:\Users\27954\Documents\github\TCM-Assistant-d2mp2-mergecheck
```

Commands:

```text
git worktree add -B tmp/d2mp2-mergecheck ..\TCM-Assistant-d2mp2-mergecheck origin/main
git merge --no-ff --no-commit port/device2-local-lora-current-interface
```

Result: passed. Git reported `Automatic merge went well; stopped before committing as requested`.

Conflict files: none.

Cleanup completed:

```text
git merge --abort
git worktree remove ..\TCM-Assistant-d2mp2-mergecheck --force
git branch -D tmp/d2mp2-mergecheck
```

## Validation

All required validation was run in the temporary merge-check worktree while the simulated merge was present.

| Check | Result | Evidence |
| --- | --- | --- |
| `python -m compileall -q app scripts tests` | passed | exit code 0 |
| `python -m unittest discover -s tests` | passed | `Ran 438 tests`, `OK (skipped=1)` |
| `python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json` | passed | `status=ok`, `finding_count=0`, `scanned_files=766` |
| `python scripts/verify_device2_local_lora_port.py --json --output reports/device2/local_lora_port_verification.json` | passed | `status=ok` |
| `python scripts/check_release_packaging.py --json --output reports/device2/d2mp2_release_packaging_check.json` | passed | `status=ok`, `checks_passed=12/12` |

The verifier script is at `scripts/verify_device2_local_lora_port.py`; there is no `scripts/device2` directory on this port branch.

Live vLLM smoke remains skipped by default: `RUN_LOCAL_VLLM_SMOKE is not enabled`.

## Interface Guards

- `BackendResult` runtime/test check: passed. `git grep -n "BackendResult" -- app tests` returned no matches. The only broader `app tests scripts` match is the verifier's own sentinel string used to enforce absence.
- Old exact `extract_turn(state, user_input)` dependency: passed. `git grep -n "extract_turn(state, user_input)" -- app tests scripts` returned no matches.
- Current extractor interface: passed. `local_lora` / `local_vllm` use `extract(user_input, *, state=...) -> ExtractorResult`.
- Router registration: passed. `app/extractors/router.py` registers both `local_lora` and `local_vllm`.
- TurnOutput / Pydantic schema guard: passed.
- Malformed JSON guard: passed.
- Risk-rules fallback: passed. Local-LoRA output remains a candidate `TurnOutput`; the risk rules layer remains the final authority and cannot be bypassed by local model output.
- Default tests do not require GPU/vLLM: passed. Live vLLM remains opt-in through `RUN_LOCAL_VLLM_SMOKE`.

## Forbidden Artifact Check

- Model weights tracked: false.
- Adapter/checkpoint payloads tracked: false.
- `.env` / secret tracked: false. `.env.example` is tracked and contains placeholders only.
- Large files added: false. Added files are small; largest added file is `scripts/verify_device2_local_lora_port.py` at 9,001 bytes.
- Secret scan: passed with `finding_count=0`.

The broad filename scan `adapter|checkpoint|safetensors|bin|pt|pth|gguf` only catches benign source/doc paths such as `workflow_adapter.py`; the strict payload scan found no weight/checkpoint extensions.

## Optional Release / Hardening Scripts

Safe offline packaging check was run:

- `scripts/check_release_packaging.py`: passed, `12/12` checks.

Broader aggregate release scripts were inspected but not run as D2-MP2 blockers:

- `scripts/verify_release_candidate_audit.py`
- `scripts/verify_p2_p10_release_hardening.py`

Reason: these are wide multi-phase release audits that rerun and rewrite broad release artifacts outside this narrow Device2 main-port merge precheck. D2-MP2 already ran the required full unittest suite, secret scan, port verifier, merge simulation, and the safe packaging check.

## Pre-existing Untracked File Handling

`reports/device2/merge_precheck.md` was inspected. It is a prior D2-MP0 blocked direct-merge precheck for `origin/feature/device2-local-lora-extractor`, not the D2-MP2 post-port merge precheck.

Final handling: preserved untouched and left untracked. D2-MP2 uses the new files:

- `reports/device2/local_lora_main_merge_precheck.md`
- `reports/device2/local_lora_main_merge_precheck.json`
- `reports/device2/local_lora_main_pr_body.md`

## D2-MP3 Recommendation

Recommended next stage: enter D2-MP3.

Suggested D2-MP3 actions:

1. Push `port/device2-local-lora-current-interface`.
2. Open a PR from the port branch to `main` using `reports/device2/local_lora_main_pr_body.md`.
3. Run hosted PR checks.
4. Merge through the normal protected main flow only after PR checks pass.

Do not directly merge to `main` during D2-MP2.
