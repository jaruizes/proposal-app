from fastapi.testclient import TestClient

from agent_platform.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "proposal-agent-platform",
        "version": "0.1.0",
    }
