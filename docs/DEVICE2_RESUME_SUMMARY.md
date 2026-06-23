# Device2 Resume Summary

Device2 built a local LoRA-backed structured extraction backend for TCM-Assistant, connected it through the existing extractor router, guarded outputs with Pydantic schema validation, and produced backend comparison artifacts for handoff.

## Technical Stack

- WSL2
- RTX 4070
- PyTorch
- Transformers
- PEFT
- TRL
- QLoRA
- vLLM
- OpenAI-compatible API
- Pydantic
- LangGraph main flow
- JSONL eval artifacts

## Project Highlights

- Local model serving path through vLLM and an OpenAI-compatible chat completions API
- LoRA single-turn structured extractor targeting the existing `TurnOutput` contract
- Multi-backend router for `fake`, `cloud_llm`, `local_base`, and `local_lora`
- `TurnOutput` schema guard before any candidate can update `RunState`
- RiskRuleEngine ownership for final risk status and red-flag projection
- Backend comparison metrics across JSON validity, schema pass rate, field match rates, risk accuracy, structured error rate, and latency
- Badcase artifacts that separate invalid JSON, skipped external backends, and eval-set limits

## Resume Bullets

Conservative version:

- Built a local LoRA structured-extraction branch for TCM-Assistant, integrating a vLLM OpenAI-compatible backend behind an existing extractor interface and documenting safe handoff constraints.

Standard version:

- Implemented a switchable local LoRA extraction backend with Pydantic `TurnOutput` validation, no-write schema failure behavior, rule-owned risk projection, and regression metrics comparing `fake`, `local_base`, `local_lora`, and skipped `cloud_llm` modes.

Interview expansion version:

- Designed and validated a Device2 Local-LoRA Extractor path: prepared WSL2/GPU runtime gates, trained and evaluated LoRA adapters outside the repository, served the adapter through a local OpenAI-compatible API, integrated it as an `ExtractorBackend`, and added verifiers, focused tests, backend metrics, badcase samples, and handoff docs. The branch deliberately keeps clinical risk authority in deterministic rules and treats model output as a schema-gated extraction candidate only.

## Interview Talking Points

Why only fine-tune the extractor instead of the whole consultation system:

The main system already owns session state, safety policy, report generation, storage, and public API contracts. A narrow extractor is easier to validate, easier to roll back, and less likely to change user-facing behavior outside the intended boundary.

Why risk rules stay outside LoRA:

Risk status is safety-critical and must be deterministic, auditable, and regression-testable. The LoRA path can help extract candidate fields, but final red-flag ownership belongs to `RiskRuleEngine`.

Why support multiple backends:

`fake` keeps deterministic tests stable, `cloud_llm` preserves the existing provider path, `local_base` provides a no-adapter baseline, and `local_lora` measures the branch's intended improvement. Comparing them makes regressions visible and avoids tying tests to one runtime.

Why schema failure cannot write `RunState`:

`RunState` is the durable source of consultation state. If the extractor emits invalid JSON or a schema-invalid payload, merging it would turn a parsing issue into corrupted application state. The graph therefore fails closed for that turn.

Why the D2-P6C seven-case eval is an engineering regression, not a broad conclusion:

The built-in D2-P6C set has only seven cases and the requested broader `eval_extract`, `eval_negation`, and `eval_risk` JSONL files are absent. It is useful for local regression and backend comparison, but it cannot support broad medical, product, or deployment claims.

## Boundary Language

Use grounded wording:

- structured extraction backend
- schema-gated candidate output
- local runtime integration
- engineering regression metrics
- handoff-ready branch

Avoid inflated wording:

- deployment-level clinical claims
- broad proof claims from the seven-case regression set
- autonomous care decisions
- treatment or formula advice
- replacement of licensed professionals
