from fastapi.testclient import TestClient

from agent_platform.api.state import agents, skills
from agent_platform.main import app

client = TestClient(app)


def setup_function() -> None:
    agents.clear()
    skills.clear()


def skill_payload() -> dict:
    return {
        "key": "review-openshift-architecture",
        "name": "Review OpenShift architecture",
        "objective": "Review an OpenShift architecture.",
        "instructions": "Assess the architecture and identify risks and improvements."
    }


def payload() -> dict:
    return {
        "key": "openshift-specialist",
        "name": "OpenShift Specialist",
        "description": "Specialist in OpenShift architecture.",
        "role": "Provide expert guidance on OpenShift.",
        "capabilities": ["openshift", "kubernetes", "platform-engineering"],
        "skills": ["review-openshift-architecture"],
        "knowledge_scopes": ["openshift"],
        "allowed_tools": ["redhat-docs"],
    }


def test_agent_crud_contract_and_registry_versioning() -> None:
    assert client.post("/v1/skills", json=skill_payload()).status_code == 201
    created = client.post("/v1/agents", json=payload() | {"version": 99})
    assert created.status_code == 201
    assert created.headers["location"] == "/v1/agents/openshift-specialist"
    assert created.json()["version"] == 1

    fetched = client.get("/v1/agents/openshift-specialist")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "OpenShift Specialist"

    listed = client.get("/v1/agents")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    updated_payload = payload() | {"description": "Updated specialist", "version": 1}
    updated = client.put("/v1/agents/openshift-specialist", json=updated_payload)
    assert updated.status_code == 200
    assert updated.json()["description"] == "Updated specialist"
    assert updated.json()["version"] == 2


def test_duplicate_agent_is_rejected() -> None:
    assert client.post("/v1/skills", json=skill_payload()).status_code == 201
    assert client.post("/v1/agents", json=payload()).status_code == 201
    assert client.post("/v1/agents", json=payload()).status_code == 409


def test_agent_rejects_unknown_skill_reference() -> None:
    response = client.post("/v1/agents", json=payload())
    assert response.status_code == 422
    assert "Unknown skill references" in response.json()["detail"]
