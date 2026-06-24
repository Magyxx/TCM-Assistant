# D2-MP4 Post-Merge Main Stabilization & Device2 Interface Seal

## Stage

D2-MP4 seals the post-merge `main` baseline after PR #2 merged the Device2 local LoRA port. This stage does not retrain LoRA, does not start a live vLLM service, does not alter model weights, and does not change business or medical safety semantics.

## Main State

- Repository: `https://github.com/Magyxx/TCM-Assistant.git`
- Branch: `main`
- Baseline local HEAD before this seal commit: `ee89f8e10c8db82724999b05b6c81c6cb694f8f4`
- Baseline `origin/main` after `git fetch origin main`: `ee89f8e10c8db82724999b05b6c81c6cb694f8f4`
- PR #2 merge commit: `ee89f8e10c8db82724999b05b6c81c6cb694f8f4`
- Merge parents:
  - `56f69eb2693fe3eecd4f1baf43603798d3b2aff9`
  - `64610dea281bba2a83eaf1a6075e64355e52f145`
- Port commit contained in `main`: yes
- Merge method: merge commit

## Device2 Interface Seal

- `local_lora` registered in `app/extractors/router.py`: yes
- `local_vllm` registered in `app/extractors/router.py`: yes
- Unified extractor router retained: yes, through `build_extractor_backend_registry()` and `get_extractor_backend()`
- Cloud/fake/fallback paths retained: yes, `fake`, `auto`, `fallback`, `rule_fallback`, `real_llm`, `openai_compatible`, and `cloud_llm` remain registered
- Old `extract_turn(state, user_input)` dependency absent from Device2 port paths: yes
- `BackendResult` residue under tests: absent

## Safety Boundary

- `local_lora` produces only candidate `TurnOutput` JSON extraction.
- Candidate output must pass the current `TurnOutput` schema guard.
- Malformed JSON is rejected and routed through auditable fallback metadata.
- Final risk status remains owned by the main risk rules layer and fallback path.
- The local LoRA backend does not diagnose, prescribe, replace a clinician, or decide final risk authority.
- RAG evidence does not overwrite core consultation state.
- `local_lora` does not override high-risk authority or sticky risk signals.

## Artifact Housekeeping

Validation refreshed local generated artifacts during D2-MP3R and again during D2-MP4 verification. The refreshed files were restored to the repository baseline so the post-merge worktree remains narrow and auditable.

Restored generated artifact diffs:

- `artifacts/p10/api_events.jsonl`
- `artifacts/p3_2_observability.json`
- `artifacts/p6_knowledge_pipeline.json`
- `artifacts/p6b_runtime_rag_trace_samples.json`
- `artifacts/p6b_runtime_rag_validation.json`
- `artifacts/p6c_evidence_metadata_audit.jsonl`
- `artifacts/p9m2/graph_events.jsonl`
- `artifacts/secret_scan_result.json`
- `knowledge/eval/p6_retrieval_safety_eval.json`
- `knowledge/indexes/p6_bm25_index.json`

Kept as D2-MP4 evidence:

- `docs/D2_MP4_POST_MERGE_MAIN_BASELINE.md`
- `artifacts/device2/d2_mp4_post_merge_baseline.json`
- `reports/device2/local_lora_port_verification.json`

Removed local-only files: none.

Expected final worktree after committing the D2-MP4 evidence: clean.

## Tag Protection

- Tag: `v0.10.0-rc3`
- Tag object: `896e60e6509041b9d89d7d14d13ed6167a9447bd`
- Peeled commit: `5c404f245172736bdb5b8ad515a3fbbcb9251c12`
- Unchanged: yes

## Validation Results

- `git fetch origin main`: passed
- `git rev-parse HEAD`: `ee89f8e10c8db82724999b05b6c81c6cb694f8f4` before this seal commit
- `git rev-parse origin/main`: `ee89f8e10c8db82724999b05b6c81c6cb694f8f4` before this seal commit
- `git show --no-patch --pretty=%P HEAD`: expected PR #2 merge parents
- `git merge-base --is-ancestor 64610dea281bba2a83eaf1a6075e64355e52f145 main`: passed
- `python -m compileall -q app scripts tests`: passed
- `python -m unittest discover -s tests`: passed, `438` tests, `skipped=1`
- `python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json`: passed, `finding_count=0`
- `python scripts/verify_device2_local_lora_port.py --json --output reports/device2/local_lora_port_verification.json`: passed
- `python scripts/check_release_packaging.py`: passed, `12/12`
- Schema guard: passed
- Malformed JSON guard: passed
- Risk rules fallback: passed
- Tracked model weights or binary checkpoints: none matched
- Exact `.env`: none tracked
- Live vLLM smoke: skipped because `RUN_LOCAL_VLLM_SMOKE` is not enabled

## Conclusion

Status: ok.

The PR #2 merge commit is a stable post-merge baseline for continued `main` development. Device2 local LoRA/vLLM entry points are sealed behind the current extractor interface, with schema validation and main-system risk authority intact.

Recommended next step: begin the mainline P10/P11 post-LoRA regression baseline, or run live vLLM smoke separately on a prepared Device2 host with `RUN_LOCAL_VLLM_SMOKE=1`. Do not mix training artifacts, checkpoints, or live-serving setup into this D2-MP4 main baseline.
