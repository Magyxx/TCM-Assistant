from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.extractors.local_lora_extractor import DEFAULT_LOCAL_LORA_MODEL, extract_with_local_lora  # noqa: E402
from app.extractors.local_vllm_extractor import DEFAULT_LOCAL_LLM_BASE_URL  # noqa: E402
from app.schemas.report_schemas import RunState  # noqa: E402


def _enabled() -> bool:
    return os.getenv("RUN_LOCAL_VLLM_SMOKE", "").strip().lower() in {"1", "true", "yes"}


def _write_payload(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Optional live smoke test for the local LoRA extractor backend.")
    parser.add_argument("--base-url", default=os.getenv("LOCAL_LLM_BASE_URL") or DEFAULT_LOCAL_LLM_BASE_URL)
    parser.add_argument("--model", default=os.getenv("LOCAL_LLM_MODEL") or DEFAULT_LOCAL_LORA_MODEL)
    parser.add_argument("--api-key", default=os.getenv("LOCAL_LLM_API_KEY") or "EMPTY")
    parser.add_argument("--input", default="胃胀两天，没有胸痛，也没有呼吸困难。")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    enabled = _enabled()
    payload: dict[str, Any] = {
        "stage": "D2-P6A_LOCAL_LORA_LIVE_SMOKE",
        "enabled": enabled,
        "base_url": args.base_url,
        "model": args.model,
        "status": "skipped",
        "reason": "RUN_LOCAL_VLLM_SMOKE is not enabled",
    }

    if enabled:
        result = extract_with_local_lora(
            RunState(),
            args.input,
            base_url=args.base_url,
            model=args.model,
            api_key=args.api_key,
            allow_fallback=False,
        )
        payload.update(
            {
                "status": "passed" if result.success and result.schema_valid else "failed",
                "reason": None if result.success and result.schema_valid else result.error,
                "json_valid": result.json_valid,
                "schema_pass": result.schema_valid and result.final_schema_pass,
                "fallback_used": result.fallback_used,
                "error_type": result.error_type,
                "latency_ms": result.latency_ms,
                "turn_output": result.turn_output.model_dump() if result.turn_output else None,
            }
        )

    _write_payload(args.output, payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"local_lora live smoke: {payload['status']} ({payload['base_url']} {payload['model']})")
    return 0 if payload["status"] in {"passed", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
