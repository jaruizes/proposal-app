from fastapi.testclient import TestClient

from agent_platform.api.state import agents, executions, skills
from agent_platform.domain import AgentDefinition, SkillDefinition
from agent_platform.main import app

client = TestClient(app)


def setup_function() -> None:
    agents.clear()
    skills.clear()
    executions.clear()
    agents["business-analyst"] = AgentDefinition(
        key="business-analyst",
        name="Business Analyst",
        role="Analyze business opportunities.",
        skills=["analyze-opportunity"],
    )
    skills["analyze-opportunity"] = SkillDefinition(
        key="analyze-opportunity",
        name="Analyze opportunity",
        objective="Understand the opportunity.",
        instructions="Analyze the supplied context and identify facts, assumptions and questions.",
    )


def test_execution_contract_creates_queued_execution() -> None:
    response = client.post(
        "/v1/executions",
        json={
            "agent_key": "business-analyst",
            "skill_key": "analyze-opportunity",
            "objective": "Analyze this opportunity",
            "context": {"offer_id": "offer-123"},
        },
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "QUEUED"
    assert body["agent_key"] == "business-analyst"

    fetched = client.get(f"/v1/executions/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]


def test_execution_requires_registered_agent_and_skill() -> None:
    missing_agent = client.post(
        "/v1/executions",
        json={"agent_key": "unknown-agent", "objective": "Do work"},
    )
    assert missing_agent.status_code == 404

    missing_skill = client.post(
        "/v1/executions",
        json={"agent_key": "business-analyst", "skill_key": "unknown-skill", "objective": "Do work"},
    )
    assert missing_skill.status_code == 404


def test_execution_events_exposes_sse_snapshot() -> None:
    created = client.post(
        "/v1/executions",
        json={"agent_key": "business-analyst", "objective": "Analyze this opportunity"},
    )
    execution_id = created.json()["id"]

    events = client.get(f"/v1/executions/{execution_id}/events")
    assert events.status_code == 200
    assert events.headers["content-type"].startswith("text/event-stream")
    assert "event: execution" in events.text
    assert '"status":"QUEUED"' in events.text
