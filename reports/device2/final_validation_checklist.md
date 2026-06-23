# Device2 Final Validation Checklist

## Documentation

- [x] `README_DEVICE2.md` exists
- [x] `docs/DEVICE2_RESUME_SUMMARY.md` exists
- [x] `docs/DEVICE2_BRANCH_HANDOFF.md` exists
- [x] `docs/DEVICE2_FINAL_USAGE.md` exists
- [x] `reports/device2/final_summary.md` exists
- [x] `reports/device2/final_badcase_summary.md` exists

## Caveats

- [x] D2-P6C seven-case minimal eval caveat documented
- [x] missing `eval_extract`, `eval_negation`, and `eval_risk` caveat documented
- [x] `cloud_llm` skipped caveat documented
- [x] live vLLM smoke skipped unless `RUN_LOCAL_VLLM_SMOKE=1` caveat documented
- [x] full unittest discover pre-existing blockers caveat documented

## Prior Artifacts

- [x] `artifacts/device2/d2_p6_integration_validation.json`
- [x] `artifacts/device2/d2_p6b_e2e_validation.json`
- [x] `artifacts/device2/d2_p6c_backend_compare_validation.json`
- [x] `artifacts/device2/d2_p6c_backend_metrics.json`
- [x] `artifacts/device2/d2_p6c_backend_predictions.sample.jsonl`
- [x] `artifacts/device2/d2_p6c_backend_badcases.sample.jsonl`

## Safety and Repository Hygiene

- [x] no clinical readiness claim
- [x] no prescription recommendation claim
- [x] risk-rule ownership documented
- [x] model weights not tracked
- [x] secret scan expected to pass with `finding_count=0`

## Handoff Recommendation

D2-P7 is acceptable when `scripts/device2/verify_d2_p7_final.py` reports `status=ok`, focused tests pass, P6B/P6C verifiers pass, secret scan passes, and final `git status --short` is clean after commit.

