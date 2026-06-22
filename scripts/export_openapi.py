from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

OPENAPI_PATH = ROOT_DIR / "artifacts" / "p10" / "openapi.json"


def export_openapi() -> Path:
    from app.api.main import app

    OPENAPI_PATH.parent.mkdir(parents=True, exist_ok=True)
    OPENAPI_PATH.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return OPENAPI_PATH


def main() -> int:
    path = export_openapi()
    print(str(path.relative_to(ROOT_DIR)).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
