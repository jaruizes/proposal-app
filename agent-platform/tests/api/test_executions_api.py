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
        skills=["qualify-opportunity"],
    )
    skills["qualify-opportunity"] = SkillDefinition(
        key="qualify-opportunity",
        name="Qualify opportunity",
        objective="Understand and qualify the opportunity.",
        instructions="Analyze the supplied context and identify facts, assumptions and questions.",
    )


def test_execution_contract_runs_agent_and_returns_result() -> None:
    response = client.post(
        "/v1/executions",
        json={
            "agent_key": "business-analyst",
            "skill_key": "qualify-opportunity",
            "objective": "Analyze this opportunity",
            "context": {"offer_id": "offer-123"},
        },
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "QUEUED"
    execution_id = body["id"]

    result = client.get(f"/v1/executions/{execution_id}/events")
    assert result.status_code == 200
    assert "event: execution.completed" in result.text
    assert "event: execution.result" in result.text

    fetched = client.get(f"/v1/executions/{execution_id}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "COMPLETED"
    assert fetched.json()["model"] == "claude-test"
    assert fetched.json()["usage"]["input_tokens"] == 100
    assert fetched.json()["provider_request_id"] == "msg_test_123"


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


def test_execution_events_exposes_full_lifecycle() -> None:
    created = client.post(
        "/v1/executions",
        json={"agent_key": "business-analyst", "objective": "Analyze this opportunity"},
    )
    execution_id = created.json()["id"]

    events = client.get(f"/v1/executions/{execution_id}/events")
    assert events.status_code == 200
    assert events.headers["content-type"].startswith("text/event-stream")
    assert "event: execution.queued" in events.text
    assert "event: execution.running" in events.text
    assert "event: execution.completed" in events.text
    assert "event: execution.result" in events.text
