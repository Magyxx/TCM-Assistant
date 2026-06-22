# Branching Policy

## Release Line

The current release line is:

```text
P7 freeze
  -> GitHub upload
  -> P7.5 branch contract / extractor contract / LangGraph skeleton
  -> tag: v0.7.5-branch-contract
      -> dev/p8-agentic-workflow
      -> exp/sft-lora-extractor
```

## P7 Freeze

P7 is the stable local baseline for service, storage, memory, tools,
observability, safety, and gate evidence.

Recommended marker:

```bash
git tag v0.7.0-p7-caution
```

Use `v0.7.0-p7-ok` only after the same P7 gate passes Docker smoke on a
Docker-capable machine.

## P7.5 Branch

P7.5 is a bridge phase. It should remain narrow:

- branch contract
- extractor contract
- LangGraph skeleton
- preservation of frozen P7 public API bodies
- preservation of safety boundaries

P7.5 should not become broad P8 agentic workflow development.

Recommended marker:

```bash
git tag v0.7.5-branch-contract
```

## P8 Development Branch

Use:

```text
dev/p8-agentic-workflow
```

P8 can expand controlled workflow behavior only after P7.5 contracts are
explicit and tested.

## SFT/LoRA Experiment Branch

Use:

```text
exp/sft-lora-extractor
```

This is the Device 2 entry branch after P7 is published to GitHub. SFT/LoRA
work remains experimental and extractor-focused. It must not mix model weights,
adapters, checkpoints, or training caches into the main release line.

The branch may prepare datasets, prompts, adapters around the existing schema,
and offline validation harnesses. It must not:

- directly write `risk_status`
- bypass Pydantic schema validation or rule merge
- mutate frozen P1/P3 response bodies
- commit real patient private data
- commit model weights, LoRA adapters, checkpoints, runs, wandb, mlruns, or
  cache directories

## Mainline Rules

- Keep release tags immutable after upload.
- Preserve the frozen API contract unless a future explicit contract review
  approves an additive migration path.
- Keep Docker-only caution distinct from functional failures.
- Keep private data, weights, adapters, and training caches out of version
  control.
