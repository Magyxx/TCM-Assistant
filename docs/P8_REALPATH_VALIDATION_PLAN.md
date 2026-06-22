# P8 / P0.2 Real-Path Validation Plan

Status date: 2026-06-22

## Purpose

P8 / P0.2 validates real runtime paths without broad product expansion. The
goal is to compare fake, fallback, and real-LLM extractor modes; exercise the
optional LangGraph runtime; smoke-test the BM25 path; and write artifacts that
make skipped or unavailable real dependencies explicit.

This phase does not train LoRA, does not start P8 product development, and does
not change the frozen P1/P3 API contract.

## Safety Boundary

TCM-Assistant remains a structured inquiry assistant. It must not diagnose,
prescribe, replace clinicians, or create treatment plans.

Hard boundaries:

- risk status comes from deterministic rules or auditable structured evidence
- LLM output must pass Pydantic validation before merge
- high-risk `present` must not be downgraded by ordinary later text
- negated risk text such as "no chest pain" must not become risk present
- RAG can enrich impression, advice, and evidence only
- RAG must not overwrite `chief_complaint`, `duration`, `risk_flags_status`,
  `triggered_rule_ids`, or other core state fields
- real LLM probes must skip safely when key, base URL, model, or dependencies
  are unavailable

## Scope

Allowed in this phase:

- optional `app.graph` facade over the existing `app.graphs` runtime
- extractor boundary modules around fake, fallback, and OpenAI-compatible paths
- BM25 realpath smoke tests
- unified verifier artifact at `artifacts/p8_realpath_validation.json`
- comparison metrics for fake, fallback, and real LLM availability

Out of scope:

- LoRA training or adapter generation
- committing model weights, adapters, checkpoints, runs, wandb, mlruns, or
  caches
- multi-agent workstation, MCP server, GraphRAG, message queues, Kubernetes, or
  full doctor backend work
- direct mutation of frozen `/sessions`, `/turn`, `/state`, or `/report`
  top-level response bodies

## Verification

Run:

```bash
python -m compileall -q app scripts tests
python -m unittest discover -s tests
python scripts/secret_scan.py --json --output artifacts/secret_scan_result.json
python scripts/verify_p8_realpath.py --json --output artifacts/p8_realpath_validation.json
```

`verify_p8_realpath.py` records:

- command return code, duration, stdout/stderr tails, timeout status, and
  parsed unittest `Ran ... OK` signal when available
- fake extractor smoke metrics
- rule fallback extractor smoke metrics
- real LLM availability and safe skip reason
- BM25 availability, retriever type, evidence count, and core-state immutability
- LangGraph facade runtime metadata
- skipped tests and skipped probes

If unittest output contains `Ran ... OK` but the outer command times out, the
artifact must record that as a runner timeout classification rather than
claiming a behavioral test failure.

## Acceptance

P8 realpath validation is acceptable when:

- compileall passes
- unittest either returns 0 or is explicitly classified as
  `content_ok_runner_timeout`
- secret scan returns `status=ok` with no findings
- fake and fallback extractors produce schema-valid `TurnOutput`
- fallback risk detection marks high-risk text as present through rules
- real LLM is either measured or safely skipped with explicit missing config
- BM25 returns evidence or records an explicit dependency/path failure
- RAG and BM25 smoke leave core state unchanged
- LangGraph facade returns either `langgraph` or `sequential_fallback` runtime
  metadata without crashing

Known cautions are acceptable when they are environment-limited and recorded,
for example missing Docker, missing real LLM config, or optional dependency
absence.
