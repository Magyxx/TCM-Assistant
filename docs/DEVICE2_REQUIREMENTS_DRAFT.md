# DEVICE2_REQUIREMENTS_DRAFT

Stage: D2-P0B Environment Readiness & Dependency Draft

Related file: `requirements-device2.txt`

## 1. Purpose

`requirements-device2.txt` is a planning draft for the future Device2 local
base/local LoRA extractor path. It is not installed in D2-P0B and it is not a
lockfile.

The existing runtime dependencies remain in `requirements.txt`; the existing
development-only tools remain in `requirements-dev.txt`.

## 2. Dependency Groups

### Core Utilities

* `python-dotenv`
* `pyyaml`
* `rich`
* `tqdm`
* `jsonlines`

These support configuration loading, YAML/JSONL handling, and readable local
tool output.

### Data and Validation

* `pydantic>=2`
* `numpy`
* `pandas`
* `scikit-learn`

These support schema validation, tabular inspection, and lightweight metrics.
The final extractor output should still align to the existing `TurnOutput`
schema.

### Training and Adapter Stack

* `torch`
* `transformers`
* `datasets`
* `accelerate`
* `peft`
* `trl`
* `bitsandbytes`
* `safetensors`
* `sentencepiece`
* `protobuf`

This group is for a later controlled local LoRA phase. D2-P0B did not install
or import these libraries. Future work must pin versions after confirming
Python, CUDA, PyTorch, quantization, and GPU compatibility.

### Local Serving / API-Compatible Client

* `vllm`
* `openai`

This supports a future local OpenAI-compatible serving path. The public API
contract should not expose model internals directly.

### Optional Evaluation Helpers

* `evaluate`

This is optional and should only be kept if it helps compact extractor metrics.
Existing repository scripts such as `scripts/eval_sft_extract.py` should remain
the primary alignment point.

## 3. Current Environment Fit

Current `importlib.util.find_spec` inventory:

* discoverable: `torch`, `transformers`, `datasets`, `accelerate`, `peft`,
  `openai`, `pydantic`, `yaml`, `sklearn`, `pandas`
* not discoverable: `bitsandbytes`, `trl`, `vllm`

This means the draft is not currently satisfied. It is expected for D2-P0B.

## 4. Version Pinning Rules

Do not pin versions blindly in this phase. Pin only after:

* target OS is confirmed: WSL2/Ubuntu or native Windows
* Python version is chosen for compatibility
* PyTorch CUDA build is selected
* vLLM support is confirmed for the target platform
* bitsandbytes support is confirmed, or a fallback quantization path is chosen
* model/cache/checkpoint storage location is decided

## 5. Artifact and Safety Rules

Do not commit:

* model weights
* LoRA adapters
* checkpoints
* local model caches
* wandb/mlruns outputs
* local SQLite databases
* `.env`
* secrets
* private or real patient data

Future code should keep the existing rule-first risk checks, Pydantic schema
validation, RAG evidence boundary, report safety checks, and frozen public API
response semantics.

## 6. Recommended D2-P1 Dependency Path

Recommended order:

1. Prepare an isolated environment.
2. Confirm CUDA/GPU visibility in that exact environment.
3. Install minimal PyTorch stack first.
4. Add `transformers`, `datasets`, `accelerate`, and `peft`.
5. Add `vllm` only if the selected platform supports it cleanly.
6. Add `bitsandbytes` only after compatibility is confirmed.
7. Keep `trl` optional until the LoRA training plan needs it.
8. Run local base-model inference smoke tests before any training.
