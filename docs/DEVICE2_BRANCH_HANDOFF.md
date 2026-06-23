# Device2 Branch Handoff

## Current Branch

- Branch: `feature/device2-local-lora-extractor`
- D2-P7 baseline HEAD: `c56fbb0 eval: add device2 backend comparison metrics`

The D2-P7 commit is intentionally reported after commit creation in the handoff response; a committed file cannot contain its own final hash without changing that hash.

## Recent 10 Commits

```text
c56fbb0 eval: add device2 backend comparison metrics
547bd24 tests: add device2 local lora e2e validation
5c8b123 extractors: integrate local lora backend for device2
3fb8e31 reports: add device2 risk repair light training results
f57e2d2 training: support device2 risk repair light training
683a1e6 chore: document device2 git recovery manifest
a539feb data: add device2 risk repair datasets and configs
980b02e extractor: add deterministic risk projection for device2
1235ba5 eval: add device2 risk failure and metric audit
77364b4 feat: complete device2 train eval and vllm serving attempt
```

## Immutable History

Do not rewrite, squash, amend, or force-push these branch history commits during handoff:

- `159c3cb` Device2 repository intake baseline
- `37e0cee` environment readiness checks
- `1b4ef27` WSL runtime and storage policy
- `f6c5d0f` WSL runtime bootstrap
- `9b2547e` training runtime gate
- `77364b4` train/eval/vLLM serving attempt
- `a539feb` risk repair datasets and configs
- `3fb8e31` risk repair light training results
- `5c8b123` local_lora backend integration
- `547bd24` main-flow E2E validation
- `c56fbb0` backend comparison metrics

## Can Merge After Review

The following file categories can be considered for mainline review or cherry-pick:

- extractor backend interface and router additions
- local vLLM and local LoRA extractor code
- environment example settings
- focused tests and verifier scripts
- small JSON validation artifacts
- documentation and reports
- sample prediction JSONL files explicitly allowed by `.gitignore`

## Do Not Merge

Do not merge these categories into mainline:

- base model files
- `adapter_model.safetensors`
- checkpoints
- large predictions
- local cache directories
- `.env`
- private patient data
- runtime SQLite databases

## Merge Prerequisites

- Device1 mainline has completed P8-M3 structured extractor adapter work or an equivalent stable interface exists
- Focused tests pass
- D2-P6B, D2-P6C, and D2-P7 verifiers pass
- Secret scan passes with `finding_count=0`
- Weight tracking check shows no model weights, adapters, or checkpoints in Git
- Mainline owner agrees that the additive backend contract is ready for review

## Recommended Merge Method

- Use PR review or explicit cherry-pick
- Do not force push
- Do not overwrite `main`
- Do not overwrite the P7 freeze tag
- Keep model/runtime artifacts external to Git

## Rollback Strategy

If a cherry-pick or PR introduces regression:

1. Revert the specific integration commit instead of rewriting shared history.
2. Reset `EXTRACTOR_BACKEND` to `fake` or the previous provider path in the deployment environment.
3. Keep `ALLOW_EXTRACTOR_FALLBACK=false` unless an owner explicitly enables fallback.
4. Re-run focused extractor tests, P6B/P6C/P7 verifiers, and secret scan before retrying.

