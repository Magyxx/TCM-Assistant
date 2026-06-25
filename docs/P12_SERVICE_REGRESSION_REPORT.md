# P12 Service Regression Report

P12-M5 adds a service-level regression gate for the FastAPI runtime.

## Gates

| Gate | Requirement |
| --- | --- |
| OpenAPI export | `scripts/export_openapi.py --output artifacts/p12/openapi.json` exports the FastAPI schema. |
| Core routes | Health, session creation, turn, report, turns, and final eval routes are present in OpenAPI. |
| P12 artifacts | M1 through M4 artifacts exist and report `status=ok`. |
| P11 regression | The P11 regression artifact exists and reports `status=ok`. |
| Secret scan | In-process scan reports zero findings. |
| Release packaging | Packaging check remains 12/12. |
| Sensitive files | No tracked `.env`, DB, or model weight files are present. |
| Old artifact churn | Known historical generated artifacts are clean before the P12 artifact is written. |

## Next

P13 should focus on deployment readiness: Docker packaging, optional PostgreSQL runtime smoke, and service operations.

The verifier writes `artifacts/p12/p12_service_regression.json` and refreshes `artifacts/p12/openapi.json`.
