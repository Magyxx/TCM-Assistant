# Device2 vLLM Serving Notes

This note documents how the D2-MP1 extractor talks to a local OpenAI-compatible endpoint. It does not add vLLM, PEFT, TRL, bitsandbytes, model weights, adapters, or checkpoints to the main install path.

## Contract

The application calls:

```text
POST {LOCAL_LLM_BASE_URL}/chat/completions
```

with an OpenAI-compatible request body containing `model`, `messages`, `temperature`, and `response_format={"type": "json_object"}`.

The assistant message content must be a single JSON object compatible with `TurnOutput`. The local model must not diagnose, prescribe, or decide final risk authority.

## Example Configuration

```env
EXTRACTOR_BACKEND=local_lora
LOCAL_LLM_BASE_URL=http://127.0.0.1:8000/v1
LOCAL_LLM_MODEL=tcm-extractor-lora
LOCAL_LLM_API_KEY=dummy
LOCAL_LLM_TIMEOUT_SECONDS=30
RUN_LOCAL_VLLM_SMOKE=0
```

Use `local_vllm` only when you want the same current `ExtractorResult` protocol surfaced under a vLLM-specific backend name:

```env
EXTRACTOR_BACKEND=local_vllm
```

## Live Smoke

By default, tests do not contact a live service. To run a local smoke manually, start the isolated vLLM service and opt in:

```powershell
$env:RUN_LOCAL_VLLM_SMOKE='1'
python scripts/verify_device2_local_lora_port.py --json --output artifacts/device2_local_lora_port_validation.json
```

The default D2-MP1 validation remains valid without this live smoke because mocked OpenAI-compatible responses cover success, malformed JSON, schema mismatch, router registration, and risk-boundary behavior.

## Safety Boundary

The LoRA/vLLM response is only a candidate extraction. Pydantic validates it as `TurnOutput`, and the main graph/risk-rule layer remains the authority for final risk state.
