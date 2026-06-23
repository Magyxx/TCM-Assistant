# Device2 Local LoRA Backend

This document covers the D2-P5B extractor path:

`EXTRACTOR_BACKEND=local_lora` -> extractor router -> `local_lora_extractor` -> vLLM OpenAI-compatible API -> `tcm-extractor-lora` -> `TurnOutput` schema -> main-system risk rules.

## Backends

Supported values:

* `fake`
* `local_base`
* `local_lora`
* `cloud_llm`

`local_base` calls the vLLM base model. It defaults to `/mnt/e/models/Qwen2.5-1.5B-Instruct`.

`local_lora` calls the served LoRA model. It defaults to:

* `LOCAL_LLM_BASE_URL=http://127.0.0.1:8000/v1`
* `LOCAL_LLM_MODEL=tcm-extractor-lora`
* `LOCAL_LLM_API_KEY=EMPTY`
* `LOCAL_LLM_MAX_TOKENS=512`
* `LOCAL_LLM_TEMPERATURE=0`
* `LOCAL_LLM_RESPONSE_FORMAT=false`

`response_format=json_object` remains off for the current vLLM/xgrammar stack.

## Fallback Policy

`local_lora` does not silently fall back. API failures, JSON parse failures, and schema failures are recorded as explicit failures.

Fallback is allowed only when `ALLOW_EXTRACTOR_FALLBACK=true`, and artifacts must record `fallback_used=true`.

## Safety Boundary

The LoRA model only produces a `TurnOutput` candidate. It does not produce a final report, diagnosis, prescription, or final risk grade. Risk flags are still guarded by the main-system rule engine.

## Validation

Use:

```bash
export TMPDIR=/tmp
python scripts/device2/check_extractor_backend.py --backend local_lora --run-graph --json
python scripts/device2/run_local_lora_realpath.py --limit 20 --no-fallback
python scripts/device2/eval_backend_compare.py --limit 20
```

In WSL, keep vLLM IPC on a Linux filesystem. If `TMPDIR` points at a Windows-mounted path such as `/mnt/e/ai_artifacts/.../tmp`, vLLM can fail with a ZMQ `Operation not supported` IPC socket error.
