from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.device2.eval_compare_backends import (  # noqa: E402
    DEFAULT_BADCASES,
    DEFAULT_METRICS,
    DEFAULT_PREDICTIONS,
    DEFAULT_REPORT,
    STAGE,
    git_info,
    json_safe,
    run_backend_compare,
    write_json,
)


DEFAULT_OUTPUT = ROOT / "artifacts" / "device2" / "d2_p6c_backend_compare_validation.json"


def _status_for_backend(info: dict[str, Any]) -> str:
    status = info.get("status")
    if status == "skipped":
        return "skipped"
    if status == "passed":
        return "passed"
    if status == "passed_with_badcases":
        return "passed_with_badcases"
    return "failed"


def build_validation_payload(compare: dict[str, Any]) -> dict[str, Any]:
    git = git_info()
    checks = {
        key: "passed" if value else "failed"
        for key, value in compare["checks"].items()
        if key != "predictions_sample_safe"
    }
    backends = {
        backend: {
            "status": _status_for_backend(info),
            "case_count": info["case_count"],
            "skipped_case_count": info["skipped_case_count"],
            "skip_reason": info.get("skip_reason"),
        }
        for backend, info in compare["backends"].items()
    }
    return {
        "stage": STAGE,
        "status": "ok" if compare["status"] == "ok" and all(value == "passed" for value in checks.values()) else "failed",
        "branch": git["branch"],
        "commit": git["head"],
        "recent_commits": git["recent_commits"],
        "case_source": compare["case_source"],
        "backends": backends,
        "metrics_artifact": "artifacts/device2/d2_p6c_backend_metrics.json",
        "predictions_sample": "artifacts/device2/d2_p6c_backend_predictions.sample.jsonl",
        "badcases_sample": "artifacts/device2/d2_p6c_backend_badcases.sample.jsonl",
        "checks": checks,
        "summary": {
            "local_lora_vs_local_base": compare["local_lora_vs_local_base"],
            "badcase_type_distribution": compare["badcase_type_distribution"],
        },
        "live_vllm": compare["live_vllm"],
        "known_env_blockers": compare["known_env_blockers"],
        "safety": {
            "no_diagnosis": compare["safety"]["no_diagnosis"],
            "no_prescription": compare["safety"]["no_prescription"],
            "lora_does_not_own_final_risk": compare["safety"]["lora_does_not_own_final_risk"],
            "weights_not_tracked": compare["safety"]["weights_not_tracked"],
            "predictions_sample_safe": compare["safety"]["predictions_sample_safe"],
            "tracked_weight_findings": compare["safety"]["tracked_weight_findings"],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify D2-P6C backend compare artifacts.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    compare = run_backend_compare(
        write_artifacts=True,
        metrics_path=DEFAULT_METRICS,
        predictions_path=DEFAULT_PREDICTIONS,
        badcases_path=DEFAULT_BADCASES,
        report_path=DEFAULT_REPORT,
    )
    payload = build_validation_payload(compare)
    write_json(args.output, payload)
    if args.json:
        print(json.dumps(json_safe(payload), ensure_ascii=False, indent=2))
    else:
        print(f"D2-P6C backend compare verification: {payload['status']} -> {args.output}")
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
