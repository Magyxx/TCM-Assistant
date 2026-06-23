from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_BASE_URL = "http://127.0.0.1:8000/v1"
DEFAULT_MODEL = "tcm-extractor-lora"
DEFAULT_PROMPT = "最近胃胀，饭后明显，差不多一周，没有发热，也不胸痛。"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def extract_json_object_text(raw_text: str) -> str:
    text = (raw_text or "").strip()
    if text.startswith("```json"):
        text = text.removeprefix("```json").strip()
    if text.startswith("```"):
        text = text.removeprefix("```").strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    if text.startswith("{") and text.endswith("}"):
        return text

    start = text.find("{")
    if start < 0:
        raise ValueError("json_object_start_not_found")
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1].strip()
    raise ValueError("json_object_end_not_found")


def http_get_json(url: str, timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        body = response.read().decode("utf-8", errors="replace")
        return {"status_code": response.status, "body": json.loads(body)}


def validate_turn_output(payload: dict[str, Any]) -> tuple[str, bool | None, str | None]:
    try:
        from app.schemas.report_schemas import TurnOutput
    except Exception as exc:  # noqa: BLE001
        return "skipped", None, f"{type(exc).__name__}: {exc}"
    try:
        TurnOutput.model_validate(payload)
        return "checked", True, None
    except Exception as exc:  # noqa: BLE001
        return "checked", False, f"{type(exc).__name__}: {exc}"


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    failures: list[str] = []
    models_payload: dict[str, Any] | None = None
    response_text = ""
    parsed_json: dict[str, Any] | None = None
    schema_check = "skipped"
    schema_pass: bool | None = None
    schema_error: str | None = None

    try:
        models_payload = http_get_json(f"{args.base_url.rstrip('/')}/models", timeout=args.timeout)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        failures.append(f"GET /models failed: {type(exc).__name__}: {exc}")

    models_endpoint_ok = bool(models_payload and models_payload.get("status_code") == 200)

    try:
        from openai import OpenAI

        client = OpenAI(base_url=args.base_url, api_key=args.api_key, timeout=args.timeout)
        completion = client.chat.completions.create(
            model=args.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a structured TCM consultation extractor. "
                        "Return only one JSON object compatible with TurnOutput. "
                        "Do not diagnose or prescribe. Do not add extra keys. "
                        "Use exactly these keys: chief_complaint, duration, symptoms, "
                        "symptoms_status, sleep, appetite, stool_urine, risk_flags, "
                        "risk_flags_status, next_question, summary. symptoms and "
                        "risk_flags must be arrays of plain strings, never objects. "
                        "Example symptoms value: [\"胃胀\"]. symptoms_status and "
                        "risk_flags_status must be one of unknown, none, present."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Extract this user input into TurnOutput JSON. "
                        "For the sample, use symptoms_status='none' when no other "
                        "symptoms are present, and risk_flags_status='none' when "
                        "risk symptoms are explicitly denied. Do not return nested "
                        "objects inside symptoms or risk_flags.\n\n"
                        f"User input: {args.prompt}"
                    ),
                },
            ],
            temperature=0,
            max_tokens=args.max_tokens,
        )
        response_text = completion.choices[0].message.content or ""
    except Exception as exc:  # noqa: BLE001
        failures.append(f"chat.completions.create failed: {type(exc).__name__}: {exc}")

    chat_completion_ok = bool(response_text)
    json_parse_ok = False
    if response_text:
        try:
            parsed_json = json.loads(extract_json_object_text(response_text))
            json_parse_ok = True
        except Exception as exc:  # noqa: BLE001
            failures.append(f"response JSON parse failed: {type(exc).__name__}: {exc}")

    if parsed_json is not None:
        schema_check, schema_pass, schema_error = validate_turn_output(parsed_json)
        if schema_pass is False:
            failures.append(f"TurnOutput schema validation failed: {schema_error}")

    status = "ok"
    if not models_endpoint_ok or not chat_completion_ok:
        status = "failed"
    elif not json_parse_ok or schema_pass is False:
        status = "caution"
    elif schema_check == "skipped":
        status = "caution"

    return {
        "generated_at": utc_now(),
        "base_url": args.base_url,
        "model": args.model,
        "prompt": args.prompt,
        "models_endpoint_ok": models_endpoint_ok,
        "models_payload": models_payload,
        "chat_completion_ok": chat_completion_ok,
        "response_text": response_text,
        "json_parse_ok": json_parse_ok,
        "parsed_json": parsed_json,
        "schema_check": schema_check,
        "schema_pass": schema_pass,
        "schema_error": schema_error,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "status": status,
        "failures": failures,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test a local vLLM OpenAI-compatible API.")
    parser.add_argument("--base-url", default=os.getenv("LOCAL_LLM_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--model", default=os.getenv("LOCAL_LLM_MODEL", DEFAULT_MODEL))
    parser.add_argument("--api-key", default=os.getenv("LOCAL_LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "EMPTY")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--max-tokens", type=int, default=int(os.getenv("LOCAL_LLM_MAX_TOKENS", "512")))
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--json", action="store_true", help="Emit JSON. JSON is also the default output format.")
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_smoke(args)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
