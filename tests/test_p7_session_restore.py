from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.session_runtime import clear_session_cache, clear_sessions


class P7SessionRestoreTests(unittest.TestCase):
    def test_api_state_restores_after_cache_clear(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            old_api = os.environ.get("TCM_API_DB_PATH")
            old_p7 = os.environ.get("TCM_SQLITE_PATH")
            os.environ["TCM_API_DB_PATH"] = str(Path(temp_dir) / "api.sqlite3")
            os.environ["TCM_SQLITE_PATH"] = str(Path(temp_dir) / "p7.sqlite3")
            try:
                clear_sessions()
                client = TestClient(app, raise_server_exceptions=False)
                session = client.post("/sessions", json={"extractor_mode": "fake", "rag_enabled": True}).json()
                client.post(
                    f"/sessions/{session['session_id']}/turn",
                    json={"user_input": "胃胀一周，没有其他症状，也没有胸痛"},
                )
                clear_session_cache()
                restored = client.get(f"/sessions/{session['session_id']}/state")
            finally:
                clear_sessions()
                if old_api is None:
                    os.environ.pop("TCM_API_DB_PATH", None)
                else:
                    os.environ["TCM_API_DB_PATH"] = old_api
                if old_p7 is None:
                    os.environ.pop("TCM_SQLITE_PATH", None)
                else:
                    os.environ["TCM_SQLITE_PATH"] = old_p7

        self.assertEqual(restored.status_code, 200)
        self.assertEqual(restored.json()["turn_count"], 1)


if __name__ == "__main__":
    unittest.main()
