import os
from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from agent_platform.api.dependencies import (
    get_agent_repository,
    get_execution_repository,
    get_model_provider,
    get_skill_repository,
)
from agent_platform.bootstrap import load_bootstrap_catalog
from agent_platform.config import Settings
from agent_platform.domain import AgentDefinition, AgentExecution, SkillDefinition
from agent_platform.main import app
from agent_platform.providers import AnthropicModelProvider


class InMemoryAgentRepository:
    def __init__(self, items: dict[str, AgentDefinition]) -> None:
        self.items = items

    async def list(self): return list(self.items.values())
    async def get_by_key(self, key): return self.items.get(key)
    async def create(self, item): self.items[item.key] = item; return item
    async def update(self, item): self.items[item.key] = item; return item


class InMemorySkillRepository:
    def __init__(self, items: dict[str, SkillDefinition]) -> None:
        self.items = items

    async def list(self): return list(self.items.values())
    async def get_by_key(self, key): return self.items.get(key)
    async def create(self, item): self.items[item.key] = item; return item
    async def update(self, item): self.items[item.key] = item; return item


class InMemoryExecutionRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, AgentExecution] = {}
        self.events: dict[UUID, list[dict]] = {}

    async def get(self, execution_id): return self.items.get(execution_id)
    async def create(self, execution): self.items[execution.id] = execution; return execution
    async def update(self, execution): self.items[execution.id] = execution; return execution
    async def add_event(self, execution_id, event_type, payload):
        self.events.setdefault(execution_id, []).append({
            "event_type": event_type,
            "payload": payload,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    async def list_events(self, execution_id): return self.events.get(execution_id, [])


@pytest.mark.integration
def test_post_execution_with_bootstrapped_business_analyst_and_real_anthropic() -> None:
    if os.getenv("RUN_ANTHROPIC_INTEGRATION") != "1":
        pytest.skip("Set RUN_ANTHROPIC_INTEGRATION=1 to run the paid Anthropic integration test")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY is required")

    skills, agents = load_bootstrap_catalog()
    model_override = os.getenv("ANTHROPIC_INTEGRATION_MODEL")
    selected_agents: dict[str, AgentDefinition] = {}
    for agent in agents:
        if agent.key != "business-analyst":
            continue
        policy = agent.model_policy.model_copy(
            update={
                "preferred_model": model_override or agent.model_policy.preferred_model,
                "max_output_tokens": 256,
            }
        )
        selected_agents[agent.key] = agent.model_copy(update={"model_policy": policy})

    agent_repository = InMemoryAgentRepository(selected_agents)
    skill_repository = InMemorySkillRepository({item.key: item for item in skills})
    execution_repository = InMemoryExecutionRepository()
    settings = Settings(
        anthropic_api_key=api_key,
        anthropic_base_url=os.getenv("ANTHROPIC_BASE_URL") or None,
        anthropic_default_model=model_override or "claude-sonnet-4-6",
    )

    app.dependency_overrides[get_agent_repository] = lambda: agent_repository
    app.dependency_overrides[get_skill_repository] = lambda: skill_repository
    app.dependency_overrides[get_execution_repository] = lambda: execution_repository
    app.dependency_overrides[get_model_provider] = lambda: AnthropicModelProvider(settings=settings)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/v1/executions",
                json={
                    "agent_key": "business-analyst",
                    "skill_key": "analyze-opportunity",
                    "objective": "Validate the independent runtime against Anthropic. Keep the answer concise.",
                    "context": {
                        "customer": "Parity Test Corp",
                        "source_manifest": {"documents": []},
                        "note": "Integration smoke test; no real customer facts are supplied."
                    },
                    "constraints": {"integration_test": True}
                },
            )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "COMPLETED", body
        assert body["artifacts"]
        assert body["artifacts"][0]["type"] == "AGENT_OUTPUT"
        assert body["artifacts"][0]["content"].strip()
        assert body["model"]
        assert body["usage"]["input_tokens"] > 0
        assert body["usage"]["output_tokens"] > 0
        assert body["provider_request_id"]

        execution_id = body["execution_id"]
        persisted = execution_repository.items[UUID(execution_id)]
        assert persisted.status.value == "COMPLETED"
        assert [event["event_type"] for event in execution_repository.events[UUID(execution_id)]] == [
            "execution.queued",
            "execution.running",
            "execution.completed",
            "execution.result",
        ]
    finally:
        app.dependency_overrides.clear()
