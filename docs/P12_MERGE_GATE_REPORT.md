# P12 Merge Gate Report

P12 is ready for pull request review from `p12/service-readiness-persistence`.

## Branch

| Item | Value |
| --- | --- |
| Branch | `p12/service-readiness-persistence` |
| Head before M6 report | `bc35aaea1ed8ee4fc2fb3906d9a84c1adda38935` |
| Base | `origin/main` at `f849f25b51bdea4357033ba6ff02ae62d39c8b70` |
| Main touched | No |
| Protected tag | `v0.10.0-rc3` unchanged |

## Validation

| Command | Result |
| --- | --- |
| `python -m compileall -q app scripts tests` | Passed |
| `python -m unittest discover -s tests` | Passed, 503 tests, 1 skipped |
| `python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json` | Passed, 0 findings |
| `python scripts/check_release_packaging.py` | Passed, 12/12 |
| `python scripts/verify_p11_regression_suite.py --json --output artifacts/p11/p11_regression_suite.json` | Passed, nested 503-test run |
| `python scripts/verify_p12_service_regression.py --json --output artifacts/p12/p12_service_regression.json --openapi-output artifacts/p12/openapi.json` | Passed |
| Sensitive tracked-file scan | Passed, no matches |
| Tag object and peeled commit checks | Passed |

## Readiness

- FastAPI OpenAPI export is present at `artifacts/p12/openapi.json`.
- P12 M1-M5 artifacts are present and green.
- P11 regression remains green on the P12 branch.
- SQLite is the default local persistence backend; PostgreSQL remains schema-ready and optional for later deployment work.
- Live vLLM is skipped unless `RUN_LOCAL_VLLM_SMOKE=1`.
- No tracked `.env`, DB, model weight, or adapter checkpoint files were found.
- Historical generated artifact churn was restored before writing this report.

Recommended next phase: P13 deployment readiness, including Docker packaging, optional PostgreSQL runtime smoke, and service operations.
