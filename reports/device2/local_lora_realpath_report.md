# D2-P5B local_lora Backend Realpath Integration

Generated at: `2026-06-23T11:50:45+00:00`

Status: `ok`

## Git

* branch: `feature/device2-local-lora-extractor`
* HEAD: `3fb8e31 (HEAD -> feature/device2-local-lora-extractor) reports: add device2 risk repair light training results`
* recent stack:
  * `3fb8e31 (HEAD -> feature/device2-local-lora-extractor) reports: add device2 risk repair light training results`
  * `f57e2d2 training: support device2 risk repair light training`
  * `683a1e6 chore: document device2 git recovery manifest`
  * `a539feb data: add device2 risk repair datasets and configs`
  * `980b02e extractor: add deterministic risk projection for device2`
  * `1235ba5 eval: add device2 risk failure and metric audit`
  * `77364b4 feat: complete device2 train eval and vllm serving attempt`
  * `9b2547e chore: finalize device2 training runtime gate`
  * `6a670e9 chore: repair device2 ml runtime dependency gate`
  * `ee7bed0 chore: add device2 ml runtime dependency gate`

## Preconditions

* D2-P5A: `ok`
* vLLM env: `/home/magyxx/venvs/tcm-vllm`
* base model: `/mnt/e/models/Qwen2.5-1.5B-Instruct`
* adapter path: `/mnt/e/ai_artifacts/tcm_assistant_device2/d2t1r2/risk_repair_20260623T060605Z/adapter/final_adapter`
* model name: `tcm-extractor-lora`

## Realpath Chain

`EXTRACTOR_BACKEND=local_lora` -> extractor router -> local_lora_extractor -> `http://127.0.0.1:8000/v1` -> `model=tcm-extractor-lora` -> TurnOutput schema -> main-system risk rules

## Case Source

* case_source: `builtin`
* builtin_cases: `True`
* gold_limited: `True`

## Metrics

* case_count: `20`
* json_valid_rate: `1.0`
* schema_pass_rate: `1.0`
* fallback_rate: `0.0`
* avg_latency_ms: `1903.278`
* p95_latency_ms: `2484.946`
* failed_count: `0`
* skipped_count: `0`

## Typical Success

- case_id: `builtin_001`
  input: 胃胀一周，饭后明显，没有发热，不胸痛
  raw_output: `{"chief_complaint":"胃胀","duration":"一周","symptoms":[],"symptoms_status":"present","sleep":null,"appetite":null,"stool_urine":null,"risk_flags":[],"risk_flags_status":"none","next_question":"最近有没有出现呕血、便血、呼吸困难等情况？"}`
  parsed_json: `{"chief_complaint": "胃胀", "duration": "一周", "symptoms": [], "symptoms_status": "present", "sleep": null, "appetite": null, "stool_urine": null, "risk_flags": [], "risk_flags_status": "none", "next_question": "最近有没有出现呕血、便血、呼吸困难等情况？"}`
  schema_pass: `True`

## Typical Failure

none

## Safety Boundary

* LoRA did not decide the final risk level.
* LoRA did not generate diagnosis.
* LoRA did not generate prescriptions.
* LoRA did not bypass the main-system rule engine.
* Silent fallback is disabled unless `ALLOW_EXTRACTOR_FALLBACK=true` is explicitly configured.

## Residual Notes

* `response_format=json_object` remains disabled for this vLLM/xgrammar combination.
* WSL serving should set `TMPDIR=/tmp`; the inherited `/mnt/e/ai_artifacts/tcm_assistant_device2/tmp` path cannot host vLLM ZMQ IPC sockets.
* Full unittest discover historical failures remain non-blocking for this stage.
* If local_base/local_lora comparison is insufficient, use backend_compare_report for the concrete badcases.
