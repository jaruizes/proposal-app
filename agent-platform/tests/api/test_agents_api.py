from fastapi.testclient import TestClient

from agent_platform.api.state import agents
from agent_platform.main import app

client = TestClient(app)


def setup_function() -> None:
    agents.clear()


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


def test_agent_crud_contract() -> None:
    created = client.post("/v1/agents", json=payload())
    assert created.status_code == 201
    assert created.headers["location"] == "/v1/agents/openshift-specialist"

    fetched = client.get("/v1/agents/openshift-specialist")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "OpenShift Specialist"

    listed = client.get("/v1/agents")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    updated_payload = payload() | {"description": "Updated specialist"}
    updated = client.put("/v1/agents/openshift-specialist", json=updated_payload)
    assert updated.status_code == 200
    assert updated.json()["description"] == "Updated specialist"


def test_duplicate_agent_is_rejected() -> None:
    assert client.post("/v1/agents", json=payload()).status_code == 201
    assert client.post("/v1/agents", json=payload()).status_code == 409
