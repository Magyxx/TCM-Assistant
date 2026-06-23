# Device2 vLLM Repair Guide

Stage: `D2-P5A: vLLM Environment Repair & LoRA Serving Smoke`

## Scope

This guide repairs Device2 vLLM serving without modifying the training runtime. The
D2-T1R2 LoRA adapter remains outside Git at:

`/mnt/e/ai_artifacts/tcm_assistant_device2/d2t1r2/risk_repair_20260623T060605Z/adapter/final_adapter`

The adapter declares its base model as:

`/mnt/e/models/Qwen2.5-1.5B-Instruct`

## Environment Policy

Use WSL2/Ubuntu only. Do not install Windows-native vLLM. Do not run
`pip install -U vllm` inside the training environment
`/home/magyxx/venvs/tcm-device2-train-py312-cu126-final`.

Use an isolated serving environment named `tcm-vllm`. Conda is preferred when
available; on this device conda is not available, so the reproducible path is uv.
The working Device2 pin is:

- `torch==2.5.1+cu124`
- `torchvision==0.20.1+cu124`
- `vllm==0.6.6.post1`
- `transformers==4.45.2`
- `tokenizers==0.20.3`
- `openai==2.43.0`

```bash
/home/magyxx/venvs/tcm-device2-tools/bin/uv venv --seed --python 3.12 /home/magyxx/venvs/tcm-vllm
source /home/magyxx/venvs/tcm-vllm/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install \
  torch==2.5.1+cu124 torchvision==0.20.1+cu124 \
  --extra-index-url https://download.pytorch.org/whl/cu124
python -m pip install vllm==0.6.6.post1 openai==2.43.0
python -m pip install transformers==4.45.2 tokenizers==0.20.3
```

The earlier latest-vLLM/cu129 resolver path is intentionally not the recommended
repair path for this device because it timed out during dependency resolution.
If these pins need to change later, keep the install log and make the change only
inside the isolated serving env:

```bash
/home/magyxx/venvs/tcm-device2-tools/bin/uv pip install --python /home/magyxx/venvs/tcm-vllm/bin/python <candidate-package>
```

## Runtime Check

```bash
python scripts/device2/check_vllm_runtime.py \
  --adapter-path /mnt/e/ai_artifacts/tcm_assistant_device2/d2t1r2/risk_repair_20260623T060605Z/adapter/final_adapter \
  --json --output reports/device2/vllm_repair_check.json
```

The check records WSL GPU availability, torch CUDA, vLLM import, OpenAI client,
adapter config, adapter weights, base model path, status, failures, and
recommendations.

## Serving

Base model:

```bash
BASE_MODEL=/mnt/e/models/Qwen2.5-1.5B-Instruct \
scripts/device2/serve_vllm_base.sh
```

LoRA adapter:

```bash
scripts/device2/serve_vllm_lora.sh
```

`serve_vllm_lora.sh` infers `BASE_MODEL` from `adapter_config.json` when
`BASE_MODEL` is not set. The default served LoRA name is `tcm-extractor-lora`.
In offline WSL sessions, set `GENERATION_CONFIG=/mnt/e/models/Qwen2.5-1.5B-Instruct`
to avoid a network lookup for the default `vllm` generation config.
The LoRA script automatically uses `chat_template.jinja` from the adapter
directory when present; set `CHAT_TEMPLATE=/path/to/template.jinja` to override.

## API Smoke

Run this in another shell after starting the server:

```bash
python scripts/device2/test_vllm_api.py \
  --base-url http://127.0.0.1:8000/v1 \
  --model tcm-extractor-lora \
  --json --output reports/device2/vllm_api_smoke.json
```

The smoke test calls `GET /models`, calls `chat.completions.create` with
`temperature=0`, extracts JSON from the response, and validates `TurnOutput` when
the repository schema is importable.

## Local Extractor Smoke

Use these local defaults after the vLLM server is running:

```bash
EXTRACTOR_BACKEND=local_lora
LOCAL_LLM_BASE_URL=http://127.0.0.1:8000/v1
LOCAL_LLM_MODEL=tcm-extractor-lora
LOCAL_LLM_API_KEY=EMPTY
LOCAL_LLM_MAX_TOKENS=512
```

The minimal extractor path is `app.extractors.local_lora_extractor`. It calls the
OpenAI-compatible local endpoint, parses JSON, validates `TurnOutput`, and then
applies the existing risk-rule guard before returning.
