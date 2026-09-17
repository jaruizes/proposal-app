from fastapi.testclient import TestClient

from agent_platform.api.state import skills
from agent_platform.main import app

client = TestClient(app)


def setup_function() -> None:
    skills.clear()


def payload() -> dict:
    return {
        "key": "analyze-competitors",
        "name": "Analyze competitors",
        "description": "Find and compare relevant competitors.",
        "objective": "Identify relevant competitors and compare their capabilities.",
        "instructions": "Identify competitors, retrieve evidence, compare capabilities and identify differentiators.",
        "inputs": ["sector", "problem"],
        "knowledge_sources": ["reference-offers", "market-intelligence"],
        "allowed_tools": ["web-search"],
    }


def test_skill_crud_contract_and_registry_versioning() -> None:
    created = client.post("/v1/skills", json=payload() | {"version": 42})
    assert created.status_code == 201
    assert created.headers["location"] == "/v1/skills/analyze-competitors"
    assert created.json()["version"] == 1

    fetched = client.get("/v1/skills/analyze-competitors")
    assert fetched.status_code == 200
    assert fetched.json()["objective"].startswith("Identify relevant competitors")

    listed = client.get("/v1/skills")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    updated_payload = payload() | {"description": "Updated competitor analysis", "version": 1}
    updated = client.put("/v1/skills/analyze-competitors", json=updated_payload)
    assert updated.status_code == 200
    assert updated.json()["description"] == "Updated competitor analysis"
    assert updated.json()["version"] == 2


def test_duplicate_skill_is_rejected() -> None:
    assert client.post("/v1/skills", json=payload()).status_code == 201
    assert client.post("/v1/skills", json=payload()).status_code == 409
