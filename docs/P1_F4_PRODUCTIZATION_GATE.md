# P1-F4 Productization Gate

P1-F4 adds an executable gate for the post-P8 P1-F productization route.

The repository still contains an older P1.1-P1.6 gate and final report from the
pre-P8 line. That gate is useful history, but it is not authoritative for this
route because it treated MemoryManager and Tool Registry as non-goals. P8 made
those components part of the accepted baseline, so P1-F4 validates the current
P8-to-P1 path directly.

## Scope

P1-F4 verifies:

- P1-F0 productization foundation.
- P1-F1 BM25 evidence pack, graph metadata, and deterministic report skeleton.
- P1-F2 API exposure through both `app.api.main:app` and `app.api.app:app`.
- P1-F3 tool invocation audit and trace correlation.
- P8 memory, graph, and extractor baseline validation.
- focused productization unit tests.
- secret scan.
- `git diff --check`.

The gate does not require a real LLM, local LoRA service, embedding model,
vector store, PostgreSQL, external tool runtime, or Device2 LoRA merge.

## Command

```powershell
python scripts/verify_p1_f4_productization_gate.py
```

Machine-readable output:

```powershell
python scripts/verify_p1_f4_productization_gate.py --json --output artifacts/p1_f4_productization_gate.json
```

For a slower broad regression run, add:

```powershell
python scripts/verify_p1_f4_productization_gate.py --full-unittest
```

## Artifact

The gate writes:

- `artifacts/p1_f4_productization_gate.json`

The artifact records command results, parsed stage artifact statuses, boundary
decisions, failed command names, failed artifact names, current branch, and
current commit.

## Boundary Statement

P1-F4 preserves these boundaries:

- P8 safety boundaries remain authoritative.
- MemoryManager is allowed only as a P8 baseline component.
- Tool Registry is allowed only as an audited internal helper boundary.
- RAG evidence remains read-only for core consultation facts.
- Tool invocation requires explicit approval when a tool declares side effects.
- No diagnosis, prescription, or treatment-plan output is introduced.
- Device2 LoRA code is not merged into Device1 mainline.

## Acceptance

P1-F4 passes only when:

- all configured commands exit with code 0.
- every required P1-F/P8 artifact exists and reports `status=ok`.
- secret scan reports `finding_count=0`.
- the boundary summary marks the older P1 gate as non-authoritative for this
  route.

After P1-F4, P1-F5 strengthened report safety, redaction, and audit proofs
around the productized API paths. P1-F6 now aggregates the post-P8 route into
the final productization acceptance report.
