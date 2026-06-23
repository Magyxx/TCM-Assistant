from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEVICE2_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(DEVICE2_DIR) not in sys.path:
    sys.path.insert(0, str(DEVICE2_DIR))

from app.extractors.router import extract_with_backend_router
from app.schemas.report_schemas import RunState
from backend_eval_utils import (
    compute_backend_metrics,
    git_snapshot,
    load_eval_cases,
    summarize_record,
    utc_now,
    write_json,
    write_jsonl,
)


DEFAULT_BASE_URL = "http://127.0.0.1:8000/v1"
DEFAULT_LOCAL_BASE_MODEL = "/mnt/e/models/Qwen2.5-1.5B-Instruct"
DEFAULT_LOCAL_LORA_MODEL = "tcm-extractor-lora"
BACKENDS = ("fake", "local_base", "local_lora", "cloud_llm")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Device2 extractor backends on one eval case set.")
    parser.add_argument("--base-url", default=os.getenv("LOCAL_LLM_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--api-key", default=os.getenv("LOCAL_LLM_API_KEY", "EMPTY"))
    parser.add_argument("--local-base-model", default=os.getenv("LOCAL_BASE_LLM_MODEL", DEFAULT_LOCAL_BASE_MODEL))
    parser.add_argument("--local-lora-model", default=os.getenv("LOCAL_LLM_MODEL", DEFAULT_LOCAL_LORA_MODEL))
    parser.add_argument("--cases", default=None)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--require-local-lora", action="store_true")
    parser.add_argument(
        "--output-predictions",
        type=Path,
        default=ROOT / "reports" / "device2" / "backend_compare_predictions.jsonl",
    )
    parser.add_argument(
        "--output-metrics",
        type=Path,
        default=ROOT / "reports" / "device2" / "backend_compare_metrics.json",
    )
    parser.add_argument(
        "--output-report",
        type=Path,
        default=ROOT / "reports" / "device2" / "backend_compare_report.md",
    )
    return parser.parse_args()


def cloud_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_BASE_URL") and os.getenv("OPENAI_MODEL"))


def _skip_record(backend: str, reason: str) -> dict[str, Any]:
    return {
        "case_id": "__backend_skipped__",
        "backend": backend,
        "input": None,
        "gold": None,
        "raw_output": None,
        "parsed_json": None,
        "json_valid": False,
        "schema_pass": False,
        "fallback_used": False,
        "latency_ms": None,
        "error": reason,
        "model_name": None,
        "base_url": None,
        "error_type": "skipped",
        "schema_error": None,
    }


def run_backend(
    backend: str,
    cases: list[dict[str, Any]],
    *,
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], str | None]:
    if args.dry_run and backend != "fake":
        return [_skip_record(backend, "dry_run")], "dry_run"
    if backend == "cloud_llm" and not cloud_available():
        return [_skip_record(backend, "missing_cloud_llm_config")], "missing_cloud_llm_config"

    records: list[dict[str, Any]] = []
    for case in cases:
        if backend == "local_base":
            result = extract_with_backend_router(
                RunState(),
                case["input"],
                backend_name=backend,
                base_url=args.base_url,
                model=args.local_base_model,
                api_key=args.api_key,
                allow_fallback=False,
            )
        elif backend == "local_lora":
            result = extract_with_backend_router(
                RunState(),
                case["input"],
                backend_name=backend,
                base_url=args.base_url,
                model=args.local_lora_model,
                api_key=args.api_key,
                allow_fallback=False,
            )
        else:
            result = extract_with_backend_router(RunState(), case["input"], backend_name=backend)
        records.append(
            result.to_prediction_record(
                case_id=case["case_id"],
                input_text=case["input"],
                gold=case.get("gold"),
            )
        )
    return records, None


def write_report(path: Path, payload: dict[str, Any]) -> None:
    metrics = payload["metrics"]
    by_backend = {item["backend"]: item for item in metrics}
    local_base = by_backend.get("local_base", {})
    local_lora = by_backend.get("local_lora", {})
    comparison = "not available"
    if local_base.get("case_count") and local_lora.get("case_count"):
        if local_lora.get("schema_pass_rate", 0) > local_base.get("schema_pass_rate", 0):
            comparison = "local_lora improved schema_pass_rate versus local_base."
        elif local_lora.get("json_valid_rate", 0) > local_base.get("json_valid_rate", 0):
            comparison = "local_lora improved json_valid_rate versus local_base."
        else:
            comparison = (
                "local_lora was not significantly better than local_base in aggregate metrics; "
                "inspect badcases before the next training round."
            )
    badcase = next(
        (
            record
            for record in payload["records"]
            if record.get("backend") == "local_lora" and (record.get("error") or not record.get("schema_pass"))
        ),
        None,
    )
    lines = [
        "# D2-P5B Backend Comparison Report",
        "",
        f"Generated at: `{payload['generated_at']}`",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Backend Status",
        "",
        "| backend | status | case_count | json_valid_rate | schema_pass_rate | fallback_rate | avg_latency_ms | p95_latency_ms |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in metrics:
        lines.append(
            "| {backend} | {status} | {case_count} | {json_valid_rate} | {schema_pass_rate} | "
            "{fallback_rate} | {avg_latency_ms} | {p95_latency_ms} |".format(**item)
        )
    lines.extend(
        [
            "",
            "## Case Source",
            "",
            f"* case_source: `{payload['case_metadata']['case_source']}`",
            f"* builtin_cases: `{payload['case_metadata']['builtin_cases']}`",
            f"* gold_limited: `{payload['case_metadata']['gold_limited']}`",
            "",
            "## local_lora vs local_base",
            "",
            comparison,
            "",
            "## local_lora Badcase",
            "",
            summarize_record(badcase),
            "",
            "## Next Training Notes",
            "",
            "* Do not infer accuracy from limited gold labels.",
            "* If local_lora is not better than local_base, prioritize JSON stability, schema completeness, negation handling, and high-risk preservation in the next data round.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    cases, case_metadata = load_eval_cases(args.cases, limit=args.limit)
    records: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []
    skipped: dict[str, str] = {}

    for backend in BACKENDS:
        backend_records, skip_reason = run_backend(backend, cases, args=args)
        records.extend(backend_records)
        if skip_reason:
            skipped[backend] = skip_reason
        metrics.append(
            compute_backend_metrics(
                backend,
                backend_records,
                skipped_reason=skip_reason,
                gold_limited=bool(case_metadata.get("gold_limited", True)),
            )
        )

    by_backend = {item["backend"]: item for item in metrics}
    local_lora_status = by_backend["local_lora"]["status"]
    status = "ok"
    if args.require_local_lora and local_lora_status in {"failed", "skipped"}:
        status = "failed"
    elif any(item["status"] == "failed" for item in metrics if item["backend"] != "cloud_llm"):
        status = "caution"
    elif any(item["status"] in {"caution", "skipped"} for item in metrics):
        status = "caution"

    payload = {
        "stage": "D2-P5B backend comparison",
        "generated_at": utc_now(),
        "status": status,
        "dry_run": args.dry_run,
        "base_url": args.base_url,
        "local_base_model": args.local_base_model,
        "local_lora_model": args.local_lora_model,
        "case_metadata": case_metadata,
        "git": git_snapshot(),
        "metrics": metrics,
        "skipped": skipped,
        "records": records,
    }
    write_jsonl(args.output_predictions, records)
    write_json(args.output_metrics, {key: value for key, value in payload.items() if key != "records"})
    write_report(args.output_report, payload)

    exit_code = 1 if status == "failed" else 0
    return payload, exit_code


def main() -> None:
    payload, exit_code = run(parse_args())
    sys.stdout.write(f"{payload['status']}\n")
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
