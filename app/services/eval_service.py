from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.api.errors import ApiError, EVAL_FAILED
from app.api.redaction import redact_secrets


ROOT_DIR = Path(__file__).resolve().parents[2]
P9M2_METRICS_PATH = ROOT_DIR / "artifacts" / "p9m2" / "multiturn_metrics.json"
P10_ARTIFACT_DIR = ROOT_DIR / "artifacts" / "p10"
P10_EVAL_METRICS_PATH = P10_ARTIFACT_DIR / "api_eval_metrics.json"
P10_SMOKE_RESULT_PATH = P10_ARTIFACT_DIR / "api_smoke_result.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(redact_secrets(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


class EvalService:
    def load_metrics(self) -> dict[str, Any]:
        return _read_json(P9M2_METRICS_PATH)

    def run_or_load_p9m2_multiturn_eval(self, *, run: bool = False) -> dict[str, Any]:
        metrics: dict[str, Any] = {}
        skipped = False
        skip_reason = ""

        if run:
            completed = subprocess.run(
                [sys.executable, "scripts/eval_p9m2_multiturn.py"],
                cwd=ROOT_DIR,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
            )
            if completed.returncode != 0:
                raise ApiError(
                    EVAL_FAILED,
                    status_code=500,
                    message="P9M2 multiturn eval failed.",
                    details={
                        "return_code": completed.returncode,
                        "stdout_tail": completed.stdout[-1200:],
                        "stderr_tail": completed.stderr[-1200:],
                    },
                )
            metrics = self.load_metrics()
        else:
            metrics = self.load_metrics()
            if not metrics:
                skipped = True
                skip_reason = "p9m2_metrics_artifact_not_found"

        result = {
            "status": "skipped" if skipped else "ok",
            "metrics": metrics,
            "artifacts": {
                "p9m2_metrics": str(P9M2_METRICS_PATH.relative_to(ROOT_DIR)).replace("\\", "/"),
                "api_eval_metrics": str(P10_EVAL_METRICS_PATH.relative_to(ROOT_DIR)).replace("\\", "/"),
            },
            "skipped": skipped,
            "skip_reason": skip_reason,
        }
        _write_json(P10_EVAL_METRICS_PATH, result)
        return result

    def export_api_smoke_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        _write_json(P10_SMOKE_RESULT_PATH, payload)
        return payload


def run_or_load_p9m2_multiturn_eval(*, run: bool = False) -> dict[str, Any]:
    return EvalService().run_or_load_p9m2_multiturn_eval(run=run)


def load_metrics() -> dict[str, Any]:
    return EvalService().load_metrics()


def export_api_smoke_result(payload: dict[str, Any]) -> dict[str, Any]:
    return EvalService().export_api_smoke_result(payload)
