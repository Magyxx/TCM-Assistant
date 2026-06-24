from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_p10m2_docker_files_default_to_local_fake_backend() -> None:
    dockerfile = (ROOT_DIR / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT_DIR / "docker-compose.yml").read_text(encoding="utf-8")

    assert "EXTRACTOR_BACKEND=fake" in dockerfile
    assert "ENABLE_REAL_LLM=false" in dockerfile
    assert "SESSION_STORE_BACKEND=sqlite" in dockerfile
    assert "Qdrant" not in compose
    assert "postgres" not in compose.lower()
    assert (ROOT_DIR / ".dockerignore").exists()

