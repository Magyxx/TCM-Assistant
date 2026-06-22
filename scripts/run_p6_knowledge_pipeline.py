from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.knowledge.pipeline import (  # noqa: E402
    DEFAULT_MANIFEST_PATH,
    artifact_summary,
    exit_code_for_status,
    json_safe,
    run_p6_pipeline,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the P6 formal knowledge clean/chunk/index/eval pipeline.")
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST_PATH),
        help="Source manifest/registry JSON path. Defaults to knowledge/sources/source_registry.json.",
    )
    parser.add_argument("--json", action="store_true", help="Print the full P6 artifact JSON.")
    parser.add_argument("--no-write", action="store_true", help="Run validation without writing output artifacts.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args(argv)
    payload = run_p6_pipeline(manifest_path=Path(args.manifest), write_outputs=not args.no_write)
    if args.json:
        public_payload = {key: value for key, value in payload.items() if not key.startswith("_")}
        print(json.dumps(json_safe(public_payload), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(artifact_summary(payload))
    return exit_code_for_status(str(payload["status"]))


if __name__ == "__main__":
    raise SystemExit(main())
