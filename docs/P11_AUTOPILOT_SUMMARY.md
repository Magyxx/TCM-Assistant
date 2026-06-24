# P11 Autopilot Mainline Hardening Summary

Branch: `p11/autopilot-mainline-hardening`

Base main commit: `2338dcaca7f1f1b27ab19c9fdb4265ca649b4382`

P11 protects the post-LoRA mainline contract without editing `main`, moving
protected tags, committing model weights, committing `.env`, or requiring a live
vLLM service.

## Milestones

| Milestone | Scope | Evidence |
| --- | --- | --- |
| M1 | Post-LoRA runtime contract | `artifacts/p11/post_lora_runtime_contract.json` |
| M2 | Extractor adapter contract | `artifacts/p11/extractor_adapter_contract.json` |
| M3 | Workflow main path contract | `artifacts/p11/workflow_path_contract.json` |
| M4 | RAG evidence contract | `artifacts/p11/rag_evidence_contract.json` |
| M5 | FinalReport safety contract | `artifacts/p11/report_safety_contract.json` |
| M6 | Aggregate regression suite | `artifacts/p11/p11_regression_suite.json` |

## Main Contracts

- Extractor outputs are candidates until schema-guarded into `TurnOutput`.
- Risk status is owned by rules, not by LoRA or RAG candidates.
- RAG can add evidence, advice context, citations, and metadata, but cannot
  overwrite core inquiry or risk fields.
- FinalReport post-check blocks or rewrites diagnosis and prescription-like
  output, preserves high-risk `urgent_visit`, and keeps citation metadata.
- Live vLLM smoke remains skipped unless `RUN_LOCAL_VLLM_SMOKE=1`.

## Protected Release State

`v0.10.0-rc3` remains an annotated tag:

- tag object: `896e60e6509041b9d89d7d14d13ed6167a9447bd`
- peeled commit: `5c404f245172736bdb5b8ad515a3fbbcb9251c12`

M6 verifies this state and does not create, delete, or move tags.

## Verification

Run:

```powershell
python scripts/verify_p11_regression_suite.py --json --output artifacts/p11/p11_regression_suite.json
```

The aggregate suite runs `compileall`, full `unittest discover`, M1-M5 contract
verifiers, secret scan, release packaging checks, sensitive tracked-file checks,
tag protection checks, and live-vLLM skip-policy checks.
