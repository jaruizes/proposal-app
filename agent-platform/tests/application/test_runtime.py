from datetime import datetime, timezone
from uuid import UUID

import pytest

from agent_platform.application.models import ModelProviderError, ModelRequest, ModelResult, ModelUsage
from agent_platform.application.registries import AgentRegistry, SkillRegistry
from agent_platform.application.runtime import AgentRuntime
from agent_platform.domain import AgentDefinition, AgentExecution, AgentExecutionRequest, ExecutionStatus, SkillDefinition


class DictAgentRepository:
    def __init__(self, items: dict[str, AgentDefinition]) -> None:
        self.items = items

    async def list(self): return list(self.items.values())
    async def get_by_key(self, key): return self.items.get(key)
    async def create(self, item): self.items[item.key] = item; return item
    async def update(self, item): self.items[item.key] = item; return item


class DictSkillRepository:
    def __init__(self, items: dict[str, SkillDefinition]) -> None:
        self.items = items

    async def list(self): return list(self.items.values())
    async def get_by_key(self, key): return self.items.get(key)
    async def create(self, item): self.items[item.key] = item; return item
    async def update(self, item): self.items[item.key] = item; return item


class DictExecutionRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, AgentExecution] = {}
        self.events: dict[UUID, list[dict]] = {}

    async def get(self, execution_id): return self.items.get(execution_id)
    async def create(self, execution): self.items[execution.id] = execution; return execution
    async def update(self, execution): self.items[execution.id] = execution; return execution
    async def add_event(self, execution_id, event_type, payload):
        self.events.setdefault(execution_id, []).append({"event_type": event_type, "payload": payload, "created_at": datetime.now(timezone.utc).isoformat()})
    async def list_events(self, execution_id): return self.events.get(execution_id, [])


class SuccessfulProvider:
    async def generate(self, request: ModelRequest) -> ModelResult:
        assert "Solution Architect" in request.system_prompt
        assert '"platform": "openshift"' in request.messages[0].content
        assert request.metadata["cognitive_context"]["sections"]["business_context"] == 1
        return ModelResult(content="# Solution\nUse OpenShift.", model="claude-test", usage=ModelUsage(input_tokens=80, output_tokens=20), provider_request_id="msg_1")


class FailingProvider:
    async def generate(self, request: ModelRequest) -> ModelResult:
        raise ModelProviderError("MODEL_TIMEOUT", "timeout", retryable=True)


def runtime(provider):
    skill = SkillDefinition(key="define-solution", name="Define solution", objective="Define it", instructions="Produce a solution")
    agent = AgentDefinition(key="solution-architect", name="Solution Architect", role="Act as a Solution Architect", skills=[skill.key])
    agent_repo = DictAgentRepository({agent.key: agent})
    skill_repo = DictSkillRepository({skill.key: skill})
    execution_repo = DictExecutionRepository()
    return AgentRuntime(AgentRegistry(agent_repo, skill_repo), SkillRegistry(skill_repo), execution_repo, provider), execution_repo


@pytest.mark.asyncio
async def test_runtime_completes_and_persists_lifecycle() -> None:
    service, repository = runtime(SuccessfulProvider())
    result = await service.execute(AgentExecutionRequest(agent_key="solution-architect", skill_key="define-solution", objective="Design it", context={"platform": "openshift"}))

    assert result.status is ExecutionStatus.COMPLETED
    assert result.artifacts[0].content == "# Solution\nUse OpenShift."
    assert result.usage.total_tokens == 100
    persisted = await repository.get(result.execution_id)
    assert persisted.status is ExecutionStatus.COMPLETED
    assert [event["event_type"] for event in await repository.list_events(result.execution_id)] == [
        "execution.queued",
        "execution.running",
        "cognitive.context.built",
        "execution.completed",
        "execution.result",
    ]


@pytest.mark.asyncio
async def test_runtime_normalizes_model_failure() -> None:
    service, repository = runtime(FailingProvider())
    result = await service.execute(AgentExecutionRequest(agent_key="solution-architect", skill_key="define-solution", objective="Design it"))

    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code == "MODEL_TIMEOUT"
    assert result.error.retryable is True
    persisted = await repository.get(result.execution_id)
    assert persisted.status is ExecutionStatus.FAILED
