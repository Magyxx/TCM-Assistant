from __future__ import annotations

import json
import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

OPENAPI_PATH = ROOT_DIR / "artifacts" / "p10" / "openapi.json"


def export_openapi(output_path: Path | None = None) -> Path:
    from app.api.main import app

    path = output_path or OPENAPI_PATH
    path = path if path.is_absolute() else ROOT_DIR / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the FastAPI OpenAPI schema.")
    parser.add_argument(
        "--output",
        default=str(OPENAPI_PATH.relative_to(ROOT_DIR)),
        help="Output JSON path. Defaults to artifacts/p10/openapi.json.",
    )
    args = parser.parse_args(argv)
    path = export_openapi(Path(args.output))
    print(str(path.relative_to(ROOT_DIR)).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
