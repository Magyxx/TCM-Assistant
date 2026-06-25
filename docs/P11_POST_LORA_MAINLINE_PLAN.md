# P11 Post-LoRA Mainline Plan

## Stage Goal

P11 starts after the Device2 local LoRA/vLLM extractor port has been merged into `main`.
The mainline now has multiple extractor backends, so the next safe step is not more
training. The next safe step is a regression baseline that makes backend behavior
auditable, repeatable, and boring.

TCM-Assistant remains a consultation-assistance system, not a diagnosis system.
The mainline must keep these boundaries:

- no definitive diagnosis
- no prescription
- no replacement for clinician judgment
- high-risk signals prompt offline medical evaluation
- LLM, local_vllm, and local_lora output is only a `TurnOutput` candidate
- final risk authority stays with the main risk rules layer
- RAG evidence may support reports, but may not overwrite core consultation state
- model weights, adapters, checkpoints, `.env`, secrets, and private data stay out of git

## Why Runtime Contract First

After D2 merged, `local_lora` and `local_vllm` are available through the same router
as `fake`, `fallback`, and cloud-compatible LLM backends. That creates a product
risk if optional backends silently fail, bypass schema validation, or appear to own
risk decisions.

P11-M1 therefore freezes a mainline contract baseline:

- every backend is registered or explicitly skipped with a reason
- every extractor result is represented as an `ExtractorResult`
- every candidate is validated as `TurnOutput` before authoritative state writes
- malformed JSON is recorded and routed through auditable fallback behavior
- `fallback_used`, `schema_guard`, and skip reasons are test-visible
- local LoRA/vLLM cannot become the default backend or final risk authority

## Layered P11 Route

| Layer | Scope | Entry Condition |
| --- | --- | --- |
| P11-M1 | Post-LoRA runtime contract baseline | D2 local LoRA/vLLM has merged to `main` |
| P11-M2 | Extractor adapter contract hardening | M1 matrix, tests, and artifact pass |
| P11-M3 | Graph/workflow main path audit | M2 backend protocol is stable |
| P11-M4 | RAG evidence contract | Graph path confirms RAG cannot write core state |
| P11-M5 | FinalReport safety contract | Evidence path and report skeleton are stable |
| P11-M6 | Repeatable post-LoRA regression eval | Extractor, risk, memory, RAG, and report contracts pass |
| P11-M7 | Service and persistence readiness | Runtime contracts are stable enough for service hardening |

## P11-M1 Boundary

This pass only establishes the runtime contract baseline. It adds docs, tests, a
verification script, and a generated artifact. Minimal runtime changes are allowed
only to expose contract metadata and skip reasons.

P11-M1 does not:

- train LoRA
- start or require live vLLM
- add diagnosis, prescription, clinician back office, multi-agent workstations, MCP,
  Kafka, Kubernetes, or microservice expansion
- change the default backend away from `fake`
- let `local_lora` or `local_vllm` write authoritative `RunState`
- let RAG evidence overwrite `chief_complaint`, `duration`, `risk_status`, or risk rule ids

## Exit Criteria

P11-M1 is complete when:

- backend matrix covers `fake`, `fallback`, `real_llm`/`openai_compatible`/`cloud_llm`,
  `local_vllm`, and `local_lora`
- optional backends have explicit skip reasons when disabled or unavailable
- schema guard, malformed JSON fallback, and risk rule fallback are regression-tested
- `scripts/verify_p11_post_lora_contract.py` writes
  `artifacts/p11/post_lora_runtime_contract.json`
- required validation commands pass

After that, the next layer is P11-M2: Extractor Adapter Contract Hardening.
