from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_echo() -> None:
    response = client.post("/echo", json={"message": "hello"})

    assert response.status_code == 200
    assert response.json() == {"message": "hello", "length": 5}
