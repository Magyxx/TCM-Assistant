# DEVICE2_TASK_UNDERSTANDING

## 1. Device2 Mission

Device2 is the Local-LoRA Extractor branch for TCM-Assistant. Its long-term task is to prepare local model deployment, QLoRA/SFT fine-tuning, a LoRA-backed structured extractor, vLLM service exposure, and safe integration back into the main consultation workflow.

The mission is narrow: build a switchable local structured extraction backend. Device2 must not rebuild the main system, change the product into a diagnosis/prescription system, or take over deterministic risk rules, RAG evidence authority, safety post-checks, reports, storage schema, or the public API contract.

## 2. What Device2 Will Build

Future Device2 modules should be understood as:

1. Environment Layer
   * WSL2
   * CUDA
   * PyTorch
   * Transformers
   * PEFT
   * TRL
   * bitsandbytes
   * vLLM

2. Dataset Layer
   * synthetic train set
   * validation set
   * extraction eval set
   * negation eval set
   * risk eval set
   * badcase set

3. Schema Layer
   * `TurnOutput`
   * risk flag fields compatible with current `RunState`
   * Pydantic validation
   * JSON repair / retry

4. Training Layer
   * base model
   * tokenizer
   * LoRA config
   * QLoRA config
   * SFTTrainer or equivalent training wrapper
   * adapter checkpoint

5. Evaluation Layer
   * base predictions
   * lora predictions
   * schema metrics
   * extraction metrics
   * risk / negation metrics
   * badcase analysis

6. Serving Layer
   * vLLM base server
   * vLLM LoRA server
   * OpenAI-compatible API
   * API smoke test

7. Integration Layer
   * `local_vllm_extractor`
   * `local_lora_extractor`
   * extractor router
   * `.env` backend switch

8. Report Layer
   * environment report
   * dataset report
   * training report
   * evaluation report
   * backend comparison report
   * badcase report
   * resume summary

## 3. What Device2 Will Not Build

Device2 will not:

* build an automatic diagnosis system
* prescribe medication, formula, dosage, or treatment plans
* replace doctors or offline medical evaluation
* rewrite the main consultation workflow
* train a full multi-turn medical Agent
* let LoRA directly write authoritative risk status
* let RAG evidence mutate core fields such as `chief_complaint`, `duration`, or risk state
* change frozen P1/P3 FastAPI response bodies without explicit approval
* change P7 freeze semantics
* commit `.env`, secrets, local SQLite databases, private patient data, model weights, LoRA adapters, checkpoints, runs, `wandb`, `mlruns`, or caches

## 4. Target Data Contract

Training and inference output must align to `TurnOutput` JSON:

```text
chief_complaint
duration
symptoms
symptoms_status
sleep
appetite
stool_urine
risk_flags
risk_flags_status
next_question
summary
```

The final output must pass `TurnOutput.model_validate(...)` from `app/schemas/report_schemas.py`. After validation, the existing graph should merge it into `RunState`, then apply deterministic risk rules and safety boundaries.

The existing `app/schemas/sft_schemas.py::SFTSampleOutput` mirrors this extraction target and is a useful future dataset wrapper, but the authoritative runtime contract remains `TurnOutput`.

## 5. Target Backend Contract

The target future backend switch should support:

* `fake`
* `cloud_llm`
* `local_base`
* `local_lora`

Current mainline API backend names are different:

* `real_llm`
* `fake`
* `fallback`

Therefore a later phase should define a careful extractor/backend contract and mapping. A likely mapping is:

```text
fake       -> current deterministic fake path
cloud_llm  -> current real_llm/provider path
local_base -> local vLLM base model without adapter
local_lora -> local vLLM base model with LoRA adapter
```

This mapping must remain internal or additive until the frozen API contract explicitly permits a public mode change.

## 6. Evaluation Contract

Future Device2 evaluation should report:

* JSON valid rate
* schema pass rate
* chief_complaint F1
* duration accuracy
* symptom F1
* risk flag accuracy
* negation accuracy
* hallucination rate
* fallback rate
* latency

It should connect to existing evaluation rather than replacing it:

* reuse `scripts/eval_sft_extract.py` for TurnOutput-style core-field checks
* preserve P5/P6/P7 safety metrics such as high-risk false negatives, diagnosis/prescription violations, RAG boundary pass, and report safety violation counts
* add backend comparison artifacts that distinguish `fake`, `cloud_llm`, `local_base`, and `local_lora`

## 7. One-Week Engineering Roadmap

* D2-P0B Environment Check
* D2-P1 Local Base Inference
* D2-P2 Synthetic Dataset
* D2-P3 QLoRA/SFT Training
* D2-P4 Local Evaluation
* D2-P5 vLLM Serving
* D2-P6 Main System Integration
* D2-P7 Final Reports and Resume Summary

## 8. First Safe Next Step

The next phase should only perform environment checks and draft Device2 requirements. It should not train, download Hugging Face models, install CUDA/PyTorch/vLLM, create datasets, modify app business logic, or change the API contract without explicit approval.
