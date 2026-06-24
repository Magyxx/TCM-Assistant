from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.api.app import app
from app.api.session_runtime import clear_sessions


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["TCM_API_DB_PATH"] = str(Path(tmp) / "smoke.sqlite3")
        clear_sessions()
        client = TestClient(app)
        health = client.get("/health")
        session = client.post("/sessions", json={"extractor_backend": "fake"})
        turn = client.post(
            "/turn",
            json={"session_id": session.json()["session_id"], "user_input": "胃胀一周，饭后明显"},
        )
    ok = health.status_code == 200 and session.status_code == 200 and turn.status_code == 200
    print({"status": "ok" if ok else "failed", "health": health.status_code, "session": session.status_code, "turn": turn.status_code})
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
