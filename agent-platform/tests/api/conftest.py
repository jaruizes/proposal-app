from datetime import datetime, timezone
from uuid import UUID

from agent_platform.api.dependencies import (
    get_agent_repository,
    get_execution_repository,
    get_model_provider,
    get_skill_repository,
)
from agent_platform.api.state import agents, executions, skills
from agent_platform.application.models import ModelProvider, ModelRequest, ModelResult, ModelUsage
from agent_platform.domain import AgentDefinition, AgentExecution, SkillDefinition
from agent_platform.main import app


class InMemoryAgentRepository:
    async def list(self) -> list[AgentDefinition]:
        return list(agents.values())

    async def get_by_key(self, key: str) -> AgentDefinition | None:
        return agents.get(key)

    async def create(self, agent: AgentDefinition) -> AgentDefinition:
        agents[agent.key] = agent
        return agent

    async def update(self, agent: AgentDefinition) -> AgentDefinition:
        agents[agent.key] = agent
        return agent


class InMemorySkillRepository:
    async def list(self) -> list[SkillDefinition]:
        return list(skills.values())

    async def get_by_key(self, key: str) -> SkillDefinition | None:
        return skills.get(key)

    async def create(self, skill: SkillDefinition) -> SkillDefinition:
        skills[skill.key] = skill
        return skill

    async def update(self, skill: SkillDefinition) -> SkillDefinition:
        skills[skill.key] = skill
        return skill


class InMemoryExecutionRepository:
    events: dict[UUID, list[dict]] = {}

    async def get(self, execution_id: UUID) -> AgentExecution | None:
        return executions.get(execution_id)

    async def create(self, execution: AgentExecution) -> AgentExecution:
        executions[execution.id] = execution
        return execution

    async def update(self, execution: AgentExecution) -> AgentExecution:
        executions[execution.id] = execution
        return execution

    async def add_event(self, execution_id: UUID, event_type: str, payload: dict) -> None:
        self.events.setdefault(execution_id, []).append(
            {
                "event_type": event_type,
                "payload": payload,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def list_events(self, execution_id: UUID) -> list[dict]:
        return self.events.get(execution_id, [])


class FakeModelProvider(ModelProvider):
    async def generate(self, request: ModelRequest) -> ModelResult:
        return ModelResult(
            content="# Agent response\n\nRuntime executed successfully.",
            model=request.model or "claude-test",
            usage=ModelUsage(input_tokens=100, output_tokens=25),
            provider_request_id="msg_test_123",
            finish_reason="end_turn",
            metadata={"provider": "fake"},
        )


_agent_repository = InMemoryAgentRepository()
_skill_repository = InMemorySkillRepository()
_execution_repository = InMemoryExecutionRepository()
_model_provider = FakeModelProvider()

app.dependency_overrides[get_agent_repository] = lambda: _agent_repository
app.dependency_overrides[get_skill_repository] = lambda: _skill_repository
app.dependency_overrides[get_execution_repository] = lambda: _execution_repository
app.dependency_overrides[get_model_provider] = lambda: _model_provider
