# DEVICE2_BRANCH_BASELINE

## 1. Branches Found

Observed `git branch -a`:

```text
* feature/device2-local-lora-extractor
  main
  remotes/origin/HEAD -> origin/main
  remotes/origin/backup/main-before-p7-device1-20260622-e986065
  remotes/origin/exp/sft-lora-extractor
  remotes/origin/main
  remotes/origin/sft-local-pipeline
```

Summary:

* local active branch: `feature/device2-local-lora-extractor`
* local main branch: `main`
* remote main branch: `origin/main`
* old/related remote branches: `backup/main-before-p7-device1-20260622-e986065`, `exp/sft-lora-extractor`, `sft-local-pipeline`

## 2. Main Baseline

Main baseline:

* `main` commit hash: `eefdfecf4e53cf196ce8815087533cf810919a07`
* commit message: `docs: prepare device2 sft lora handoff`
* remote alignment: `origin/main` points to the same commit
* latest tag by creator date: `v0.7.0-p7-caution`
* P7 tag commit: `533cb38` (`freeze: P7 service storage memory tools observability gate`)

Recent log:

```text
eefdfec docs: prepare device2 sft lora handoff
533cb38 freeze: P7 service storage memory tools observability gate
6134244 add SFT LoRA local training and inference pipeline
d9bcae5 refactor(report): rename low-risk labels and add current rules doc
f23a780 init stable report baseline
```

## 3. Device2 Branch

Device2 branch:

* branch name: `feature/device2-local-lora-extractor`
* branch source: current `main`
* current commit: `eefdfecf4e53cf196ce8815087533cf810919a07`
* ancestry check: `origin/main is ancestor of HEAD: yes`
* remote tracking: no remote branch was created or pushed in D2-P0A

This branch was created for the D2-P0A documentation-only intake task. It is separate from the older remote `origin/exp/sft-lora-extractor` branch, which was not modified.

## 4. Old Branch Isolation

Old branches are read-only context for this phase:

* `origin/exp/sft-lora-extractor` already points to `eefdfec`, but this task did not switch to it.
* `origin/sft-local-pipeline` points to `6134244`, an older SFT/LoRA pipeline commit.
* `origin/backup/main-before-p7-device1-20260622-e986065` is a backup branch and must not be modified.

D2-P0A did not delete, rebase, reset, force-push, merge into, or otherwise modify any old branch.

## 5. Git Safety Rules

Future Device2 work must follow:

* no direct development on `main`
* no force push
* no reset main
* no rebase of the remote mainline
* no deletion of local or remote branches
* no blind overwrite of existing branches
* no secret
* no `.env`
* no local SQLite database
* no private patient data
* no model weights
* no LoRA adapters
* no checkpoints
* no large training artifacts
* no API contract change without explicit approval
* no P7 freeze semantic change without explicit approval
* only compact reviewed docs/code/eval artifacts may be considered for future merge
