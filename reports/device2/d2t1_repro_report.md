# D2-T1 Repro Report

Run from Ubuntu WSL in the training environment:

```bash
source ~/venvs/tcm-device2-train-py312-cu126-final/bin/activate
cd /mnt/c/Users/Administrator/Documents/TCM-Ass/TCM-Assistant
python scripts/device2/run_d2t1_train_eval.py --model-path /mnt/e/models/Qwen2.5-1.5B-Instruct --run-id d2t1_20260623_formal --num-train-epochs 20 --max-length 1024 --compute-dtype bf16
```

Expected tracked outputs:

* `artifacts/device2/d2t1_metrics.json`
* `artifacts/device2/d2t1_dataset_freeze.json`
* `reports/device2/d2t1_training_report.md`
* `reports/device2/d2t1_evaluation_report.md`
* `reports/device2/d2t1_repro_report.md`
* `reports/device2/vllm_deferred_report.md` when vLLM is unavailable

Expected untracked external outputs:

* `/mnt/e/ai_artifacts/tcm_assistant_device2/d2t1/d2t1_20260623_formal`
