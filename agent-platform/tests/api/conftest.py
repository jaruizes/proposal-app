from datetime import datetime, timezone
from uuid import UUID

from agent_platform.api.dependencies import (
    get_agent_repository,
    get_execution_repository,
    get_skill_repository,
)
from agent_platform.api.state import agents, executions, skills
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


_agent_repository = InMemoryAgentRepository()
_skill_repository = InMemorySkillRepository()
_execution_repository = InMemoryExecutionRepository()

app.dependency_overrides[get_agent_repository] = lambda: _agent_repository
app.dependency_overrides[get_skill_repository] = lambda: _skill_repository
app.dependency_overrides[get_execution_repository] = lambda: _execution_repository
