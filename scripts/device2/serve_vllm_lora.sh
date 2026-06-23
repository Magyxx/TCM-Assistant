#!/usr/bin/env bash
set -euo pipefail

: "${LORA_NAME:=tcm-extractor-lora}"
: "${LORA_PATH:=/mnt/e/ai_artifacts/tcm_assistant_device2/d2t1r2/risk_repair_20260623T060605Z/adapter/final_adapter}"
: "${HOST:=127.0.0.1}"
: "${PORT:=8000}"
: "${MAX_MODEL_LEN:=2048}"
: "${GPU_MEMORY_UTILIZATION:=0.75}"
: "${DTYPE:=auto}"
: "${MAX_LORA_RANK:=64}"
: "${GENERATION_CONFIG:=vllm}"
: "${CHAT_TEMPLATE:=}"
: "${BASE_MODEL:=}"
: "${LORA_MODULES_FORMAT:=name_path}"

if [[ -z "${TMPDIR:-}" || "${TMPDIR}" == /mnt/* ]]; then
  export TMPDIR=/tmp
fi

if [[ ! -d "${LORA_PATH}" ]]; then
  echo "LORA_PATH does not exist: ${LORA_PATH}" >&2
  exit 2
fi

if [[ -z "${BASE_MODEL}" ]]; then
  if [[ -f "${LORA_PATH}/adapter_config.json" ]] && command -v python >/dev/null 2>&1; then
    BASE_MODEL="$(python - "${LORA_PATH}/adapter_config.json" <<'PY'
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
try:
    config = json.loads(config_path.read_text(encoding="utf-8"))
except Exception:
    print("")
else:
    print(config.get("base_model_name_or_path") or "")
PY
)"
  fi
fi

if [[ -z "${BASE_MODEL}" ]]; then
  echo "BASE_MODEL is empty and could not be inferred from ${LORA_PATH}/adapter_config.json." >&2
  echo "Set BASE_MODEL=/path/or/hf-id before starting the LoRA server." >&2
  exit 2
fi

if [[ "${LORA_MODULES_FORMAT}" == "json" ]]; then
  LORA_MODULES="[{\"name\":\"${LORA_NAME}\",\"path\":\"${LORA_PATH}\"}]"
else
  LORA_MODULES="${LORA_NAME}=${LORA_PATH}"
fi

EXTRA_ARGS=()
if [[ -n "${CHAT_TEMPLATE}" ]]; then
  EXTRA_ARGS+=(--chat-template "${CHAT_TEMPLATE}")
elif [[ -f "${LORA_PATH}/chat_template.jinja" ]]; then
  EXTRA_ARGS+=(--chat-template "${LORA_PATH}/chat_template.jinja")
fi

exec vllm serve "${BASE_MODEL}" \
  --host "${HOST}" \
  --port "${PORT}" \
  --dtype "${DTYPE}" \
  --max-model-len "${MAX_MODEL_LEN}" \
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION}" \
  --generation-config "${GENERATION_CONFIG}" \
  --enable-lora \
  --max-lora-rank "${MAX_LORA_RANK}" \
  --lora-modules "${LORA_MODULES}" \
  "${EXTRA_ARGS[@]}"
