# Device2 Repo Intake Report

Stage: D2-P0A Repository Intake & Project Understanding

Result: `ok`

## Git Summary

* repo: `https://github.com/Magyxx/TCM-Assistant.git`
* clone path: `C:\Users\Administrator\Documents\TCM-Ass\TCM-Assistant`
* current branch: `feature/device2-local-lora-extractor`
* main commit: `eefdfecf4e53cf196ce8815087533cf810919a07`
* main message: `docs: prepare device2 sft lora handoff`
* latest tag: `v0.7.0-p7-caution`
* tag commit: `533cb38`
* remote branches observed: `origin/main`, `origin/exp/sft-lora-extractor`, `origin/sft-local-pipeline`, `origin/backup/main-before-p7-device1-20260622-e986065`

## Intake Conclusion

The repository was cloned successfully from GitHub. The new Device2 branch was created from latest `main`. Existing older branches were not modified. The current mainline is understandable and records P7 release freeze as the functional-complete local baseline with one Docker-only caution.

## Project Understanding

TCM-Assistant is a structured TCM inquiry assistant. It collects and organizes chief complaint, duration, symptoms, sleep, appetite, stool/urine, risk signals, and missing follow-up information. It is not a diagnosis system, prescription system, treatment planner, or clinician replacement.

The main workflow is:

```text
FastAPI
  -> P4WorkflowAdapter
  -> LangGraph consultation graph
  -> extract_turn
  -> TurnOutput validation
  -> RunState merge
  -> rule-first risk check
  -> follow-up/report decision
  -> read-only RAG evidence
  -> FinalReport
  -> safety post-check
  -> P7 persistence / trace / evidence / memory
```

## Device2 Understanding

Device2 should add a local structured extractor branch only. The future target is:

```text
user input
  -> local_lora_extractor
  -> local vLLM OpenAI-compatible API
  -> base model + LoRA adapter
  -> TurnOutput JSON
  -> Pydantic validation
  -> existing RunState merge
  -> existing rule-first risk safeguards
```

Current API modes are `real_llm`, `fake`, and `fallback`. The future Device2 target backend names are `fake`, `cloud_llm`, `local_base`, and `local_lora`; this requires a later explicit extractor/backend contract phase.

## Files Added

* `docs/DEVICE2_REPO_INTAKE.md`
* `docs/DEVICE2_TASK_UNDERSTANDING.md`
* `docs/DEVICE2_BRANCH_BASELINE.md`
* `reports/device2/repo_intake_report.md`

## Explicit Non-Actions

* Business code changed: no
* Tests changed: no
* README changed: no
* `.env.example` changed: no
* API contract changed: no
* P7 freeze semantics changed: no
* Model downloaded: no
* Training run: no
* Commit created: no
* Push performed: no

## Next Recommended Phase

Proceed only to D2-P0B Environment Check after user approval. That phase should inventory Windows/WSL2/CUDA/GPU/Python readiness and draft Device2 requirements. It should not train, download models, install heavy dependencies, or modify main business code.
