from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.knowledge.source_registry import (  # noqa: E402
    DEFAULT_SOURCE_REGISTRY_PATH,
    json_safe,
    write_json,
)
from app.knowledge.source_review import review_source_registry, source_review_hard_pass  # noqa: E402


DEFAULT_ARTIFACT = ROOT_DIR / "artifacts" / "p6c_source_review.json"


def run_p6c_source_review(
    *,
    registry_path: Path | str = DEFAULT_SOURCE_REGISTRY_PATH,
    write_artifact: bool = True,
) -> dict:
    payload = review_source_registry(registry_path=registry_path)
    payload["artifact"] = str(DEFAULT_ARTIFACT.relative_to(ROOT_DIR)).replace("\\", "/")
    if write_artifact:
        write_json(DEFAULT_ARTIFACT, payload)
    return payload


def exit_code_for_status(payload: dict) -> int:
    return 0 if source_review_hard_pass(payload) else 1


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the P6C source review workflow.")
    parser.add_argument("--registry", default=str(DEFAULT_SOURCE_REGISTRY_PATH))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv)
    payload = run_p6c_source_review(registry_path=args.registry, write_artifact=not args.no_write)
    if args.json:
        print(json.dumps(json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            "P6C source review: "
            f"status={payload['status']} "
            f"sources={payload['source_count']} "
            f"runtime={payload['approved_for_runtime_count']} "
            f"eval={payload['approved_for_eval_count']} "
            f"training={payload['approved_for_training_count']} "
            f"artifact={DEFAULT_ARTIFACT.relative_to(ROOT_DIR)}"
        )
    return exit_code_for_status(payload)


if __name__ == "__main__":
    raise SystemExit(main())
