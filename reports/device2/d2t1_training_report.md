# D2-T1 Training Report

Generated at: `2026-06-23T01:38:19+00:00`

Status: `caution`

## Runtime

* base model: `/mnt/e/models/Qwen2.5-1.5B-Instruct`
* training env: `/home/magyxx/venvs/tcm-device2-train-py312-cu126-final`
* external run dir: `/mnt/e/ai_artifacts/tcm_assistant_device2/d2t1/d2t1_20260623_formal`
* adapter path: `/mnt/e/ai_artifacts/tcm_assistant_device2/d2t1/d2t1_20260623_formal/adapter/final_adapter`
* train epochs: `20.0`
* max sequence length: `1024`
* QLoRA: `True`

## Dataset Freeze

* freeze artifact: `artifacts/device2/d2t1_dataset_freeze.json`
* freeze ok: `True`
* train rows: `16`
* val rows: `4`

## Training Result

* train runtime seconds: `92.303`
* adapter saved: `True`
* PEFT adapter load smoke: `True`

## No Large Repo Artifacts

Adapters, checkpoints, full predictions, and model cache are under the external run dir, not the repository.
