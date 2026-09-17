from uuid import UUID

from agent_platform.domain import AgentDefinition, AgentExecution, SkillDefinition


agents: dict[str, AgentDefinition] = {}
skills: dict[str, SkillDefinition] = {}
executions: dict[UUID, AgentExecution] = {}
