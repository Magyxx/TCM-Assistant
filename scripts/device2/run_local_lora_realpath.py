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
)


DEFAULT_BASE_URL = "http://127.0.0.1:8000/v1"
DEFAULT_MODEL = "tcm-extractor-lora"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the D2-P5B local_lora realpath evaluator.")
    parser.add_argument("--base-url", default=os.getenv("LOCAL_LLM_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--model", default=os.getenv("LOCAL_LLM_MODEL", DEFAULT_MODEL))
    parser.add_argument("--api-key", default=os.getenv("LOCAL_LLM_API_KEY", "EMPTY"))
    parser.add_argument("--cases", default=None)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--output-json", type=Path, default=ROOT / "reports" / "device2" / "local_lora_realpath.json")
    parser.add_argument("--output-report", type=Path, default=ROOT / "reports" / "device2" / "local_lora_realpath_report.md")
    parser.add_argument("--require-vllm", dest="require_vllm", action="store_true", default=True)
    parser.add_argument("--allow-missing-vllm", dest="require_vllm", action="store_false")
    parser.add_argument("--no-fallback", dest="allow_fallback", action="store_false", default=False)
    parser.add_argument("--allow-fallback", dest="allow_fallback", action="store_true")
    return parser.parse_args()


def write_report(path: Path, payload: dict[str, Any]) -> None:
    metrics = payload["metrics"]
    success_sample = next((record for record in payload["records"] if record.get("schema_pass")), None)
    failure_sample = next((record for record in payload["records"] if record.get("error")), None)
    git = payload["git"]
    lines = [
        "# D2-P5B local_lora Backend Realpath Integration",
        "",
        f"Generated at: `{payload['generated_at']}`",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Git",
        "",
        f"* branch: `{git.get('branch')}`",
        f"* HEAD: `{git.get('head')}`",
        "* recent stack:",
        *[f"  * `{item}`" for item in git.get("recent_commits", [])],
        "",
        "## Preconditions",
        "",
        "* D2-P5A: `ok`",
        "* vLLM env: `/home/magyxx/venvs/tcm-vllm`",
        "* base model: `/mnt/e/models/Qwen2.5-1.5B-Instruct`",
        "* adapter path: `/mnt/e/ai_artifacts/tcm_assistant_device2/d2t1r2/risk_repair_20260623T060605Z/adapter/final_adapter`",
        f"* model name: `{payload['model']}`",
        "",
        "## Realpath Chain",
        "",
        "`EXTRACTOR_BACKEND=local_lora` -> extractor router -> local_lora_extractor -> "
        f"`{payload['base_url']}` -> `model={payload['model']}` -> TurnOutput schema -> main-system risk rules",
        "",
        "## Case Source",
        "",
        f"* case_source: `{payload['case_metadata']['case_source']}`",
        f"* builtin_cases: `{payload['case_metadata']['builtin_cases']}`",
        f"* gold_limited: `{payload['case_metadata']['gold_limited']}`",
        "",
        "## Metrics",
        "",
        f"* case_count: `{metrics['case_count']}`",
        f"* json_valid_rate: `{metrics['json_valid_rate']}`",
        f"* schema_pass_rate: `{metrics['schema_pass_rate']}`",
        f"* fallback_rate: `{metrics['fallback_rate']}`",
        f"* avg_latency_ms: `{metrics['avg_latency_ms']}`",
        f"* p95_latency_ms: `{metrics['p95_latency_ms']}`",
        f"* failed_count: `{metrics['failed_count']}`",
        f"* skipped_count: `{metrics['skipped_count']}`",
        "",
        "## Typical Success",
        "",
        summarize_record(success_sample),
        "",
        "## Typical Failure",
        "",
        summarize_record(failure_sample),
        "",
        "## Safety Boundary",
        "",
        "* LoRA did not decide the final risk level.",
        "* LoRA did not generate diagnosis.",
        "* LoRA did not generate prescriptions.",
        "* LoRA did not bypass the main-system rule engine.",
        "* Silent fallback is disabled unless `ALLOW_EXTRACTOR_FALLBACK=true` is explicitly configured.",
        "",
        "## Residual Notes",
        "",
        "* `response_format=json_object` remains disabled for this vLLM/xgrammar combination.",
        "* WSL serving should set `TMPDIR=/tmp` so vLLM IPC sockets stay on the Linux filesystem.",
        "* Full unittest discover historical failures remain non-blocking for this stage.",
        "* If local_base/local_lora comparison is insufficient, use backend_compare_report for the concrete badcases.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    os.environ["EXTRACTOR_BACKEND"] = "local_lora"
    os.environ["LOCAL_LLM_BASE_URL"] = args.base_url
    os.environ["LOCAL_LLM_MODEL"] = args.model
    os.environ["LOCAL_LLM_API_KEY"] = args.api_key
    os.environ["ALLOW_EXTRACTOR_FALLBACK"] = "true" if args.allow_fallback else "false"

    cases, case_metadata = load_eval_cases(args.cases, limit=args.limit)
    records: list[dict[str, Any]] = []
    for case in cases:
        state = RunState()
        result = extract_with_backend_router(
            state,
            case["input"],
            backend_name="local_lora",
            base_url=args.base_url,
            model=args.model,
            api_key=args.api_key,
            allow_fallback=args.allow_fallback,
        )
        records.append(
            result.to_prediction_record(
                case_id=case["case_id"],
                input_text=case["input"],
                gold=case.get("gold"),
            )
        )

    metrics = compute_backend_metrics(
        "local_lora",
        records,
        gold_limited=bool(case_metadata.get("gold_limited", True)),
    )
    status = metrics["status"]
    if args.require_vllm and (metrics["case_count"] < args.limit or metrics["schema_pass_rate"] < 1.0):
        status = "failed" if metrics["schema_pass_rate"] == 0 else "caution"

    payload = {
        "stage": "D2-P5B local_lora Backend Realpath Integration",
        "generated_at": utc_now(),
        "status": status,
        "base_url": args.base_url,
        "model": args.model,
        "allow_fallback": args.allow_fallback,
        "require_vllm": args.require_vllm,
        "case_metadata": case_metadata,
        "git": git_snapshot(),
        "metrics": metrics,
        "records": records,
    }
    write_json(args.output_json, payload)
    write_report(args.output_report, payload)

    exit_code = 0
    if args.require_vllm and status in {"failed", "caution"}:
        exit_code = 1
    return payload, exit_code


def main() -> None:
    payload, exit_code = run(parse_args())
    sys.stdout.write(f"{payload['status']}\n")
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
