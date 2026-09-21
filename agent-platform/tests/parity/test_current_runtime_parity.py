from datetime import datetime, timezone
from uuid import UUID

import pytest

from agent_platform.application.models import ModelRequest, ModelResult, ModelUsage
from agent_platform.application.registries import AgentRegistry, SkillRegistry
from agent_platform.application.runtime import AgentRuntime
from agent_platform.bootstrap import load_bootstrap_catalog
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
        self.events.setdefault(execution_id, []).append({
            "event_type": event_type,
            "payload": payload,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    async def list_events(self, execution_id): return self.events.get(execution_id, [])


class RecordingProvider:
    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    async def generate(self, request: ModelRequest) -> ModelResult:
        self.requests.append(request)
        return ModelResult(
            content="# parity-ok",
            model=request.model or "claude-test",
            usage=ModelUsage(input_tokens=120, output_tokens=15),
            provider_request_id="msg_parity",
            finish_reason="end_turn",
        )


def current_runtime():
    skills, agents = load_bootstrap_catalog()
    skill_repo = DictSkillRepository({item.key: item for item in skills})
    agent_repo = DictAgentRepository({item.key: item for item in agents})
    execution_repo = DictExecutionRepository()
    provider = RecordingProvider()
    runtime = AgentRuntime(
        AgentRegistry(agent_repo, skill_repo),
        SkillRegistry(skill_repo),
        execution_repo,
        provider,
    )
    return runtime, provider, execution_repo, agent_repo, skill_repo


@pytest.mark.parametrize(
    ("agent_key", "skill_key"),
    [
        ("business-analyst", "qualify-opportunity"),
        ("business-analyst", "compose-proposal"),
        ("business-analyst", "design-presentation"),
        ("business-analyst", "generate-presentation"),
        ("solution-architect", "design-solution"),
        ("delivery-manager", "plan-delivery"),
        ("security-specialist", "design-solution"),
        ("corporate-slide-designer", "generate-presentation"),
    ],
)
@pytest.mark.asyncio
async def test_current_agent_skill_pairs_preserve_contract_and_runtime_assembly(agent_key: str, skill_key: str) -> None:
    runtime, provider, executions, agents, skills = current_runtime()
    agent = await agents.get_by_key(agent_key)
    skill = await skills.get_by_key(skill_key)
    assert agent is not None and skill is not None

    result = await runtime.execute(
        AgentExecutionRequest(
            agent_key=agent_key,
            skill_key=skill_key,
            objective="Parity validation objective",
            context={"offer_id": "offer-parity", "language": "es", "evidence": "FACT sample"},
            constraints={"do_not_estimate": True},
        )
    )

    assert result.status is ExecutionStatus.COMPLETED
    assert result.artifacts[0].content == "# parity-ok"
    assert result.artifacts[0].metadata["agent_key"] == agent_key
    assert result.artifacts[0].metadata["skill_key"] == skill_key
    assert result.usage.total_tokens == 135
    assert result.provider_request_id == "msg_parity"

    request = provider.requests[-1]
    assert agent.role in request.system_prompt
    assert skill.instructions in request.system_prompt
    assert request.system_prompt.index(agent.role) < request.system_prompt.index(skill.instructions)
    assert "# Task\nParity validation objective" in request.messages[0].content
    assert '"offer_id": "offer-parity"' in request.messages[0].content
    assert '"do_not_estimate": true' in request.messages[0].content
    assert request.model == agent.model_policy.preferred_model
    assert request.temperature == agent.model_policy.temperature
    assert request.max_output_tokens == agent.model_policy.max_output_tokens

    persisted = await executions.get(result.execution_id)
    assert persisted is not None
    assert persisted.status is ExecutionStatus.COMPLETED
    events = await executions.list_events(result.execution_id)
    assert [event["event_type"] for event in events] == [
        "execution.queued",
        "execution.running",
        "cognitive.context.built",
        "execution.completed",
        "execution.result",
    ]
    cognitive_event = events[2]
    assert cognitive_event["payload"]["items"] >= 1
    assert cognitive_event["payload"]["sections"]["business_context"] >= 1


@pytest.mark.asyncio
async def test_non_assigned_skill_is_rejected_before_model_invocation() -> None:
    runtime, provider, _, _, _ = current_runtime()

    with pytest.raises(Exception, match="Skill is not assigned to agent"):
        await runtime.execute(
            AgentExecutionRequest(
                agent_key="solution-architect",
                skill_key="plan-delivery",
                objective="This pair must not run",
            )
        )

    assert provider.requests == []
