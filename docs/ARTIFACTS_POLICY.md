# Artifacts Policy

## Purpose

Artifacts are release evidence, regression evidence, and debugging evidence.
They are not a place for secrets, private patient records, model weights, or
training caches.

## Keep In Version Control

Keep compact JSON artifacts that document gates and baselines, especially:

- P7 gate and validation reports
- P7 Docker smoke result
- P7 failure analysis
- historical P1-P6 gate reports
- API contract snapshots
- source-governance and code-health reports
- small synthetic replay/eval cases used by tests

The current P7 release evidence is:

- `artifacts/p7_gate_report.json`
- `artifacts/p7_docker_smoke.json`
- `artifacts/p7_failure_analysis.json`

## Do Not Version

Do not commit:

- `artifacts/tmp/`
- temporary traces that contain raw private text
- raw private patient input
- local SQLite runtime databases
- generated local logs
- `.env` or `.env.*`
- model weights or adapters
- checkpoints
- training outputs
- experiment tracker directories
- cache directories

## Privacy Rule

Artifacts may contain synthetic cases, aggregate metrics, schema samples, and
redacted previews. They must not contain real patient private data, full raw
private consultations, access tokens, API keys, cookies, passwords, or local
secret values.

## Docker Caution Rule

If Docker CLI is unavailable, keep the resulting Docker smoke artifact. It is
important release evidence because it explains why P7 is `caution` instead of
`ok` on the current machine.

## Artifact Refresh

Before a release freeze, refresh:

```bash
python -m unittest discover -s tests
python -m compileall -q app scripts tests
python scripts/run_p7_gate.py
```

Then review changed artifacts before committing.
