#!/usr/bin/env bash
set -euo pipefail

: "${HOST:=127.0.0.1}"
: "${PORT:=8000}"
: "${MAX_MODEL_LEN:=2048}"
: "${GPU_MEMORY_UTILIZATION:=0.75}"
: "${DTYPE:=auto}"
: "${GENERATION_CONFIG:=vllm}"
: "${CHAT_TEMPLATE:=}"
: "${BASE_MODEL:=}"

if [[ -z "${TMPDIR:-}" || "${TMPDIR}" == /mnt/* ]]; then
  export TMPDIR=/tmp
fi

if [[ -z "${BASE_MODEL}" ]]; then
  echo "BASE_MODEL is required for base vLLM serving." >&2
  echo "Example: BASE_MODEL=/mnt/e/models/Qwen2.5-1.5B-Instruct scripts/device2/serve_vllm_base.sh" >&2
  exit 2
fi

EXTRA_ARGS=()
if [[ -n "${CHAT_TEMPLATE}" ]]; then
  EXTRA_ARGS+=(--chat-template "${CHAT_TEMPLATE}")
fi

exec vllm serve "${BASE_MODEL}" \
  --host "${HOST}" \
  --port "${PORT}" \
  --dtype "${DTYPE}" \
  --max-model-len "${MAX_MODEL_LEN}" \
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION}" \
  --generation-config "${GENERATION_CONFIG}" \
  "${EXTRA_ARGS[@]}"
