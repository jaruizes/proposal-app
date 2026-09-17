from agent_platform.application.repositories import AgentRepository, SkillRepository
from agent_platform.domain import AgentDefinition, SkillDefinition


class RegistryError(Exception):
    """Base error raised by registry application services."""


class DefinitionNotFoundError(RegistryError):
    pass


class DefinitionAlreadyExistsError(RegistryError):
    pass


class InvalidDefinitionReferenceError(RegistryError):
    pass


class SkillRegistry:
    """Application service that owns the lifecycle of skill definitions."""

    def __init__(self, repository: SkillRepository) -> None:
        self._repository = repository

    async def list(self) -> list[SkillDefinition]:
        return await self._repository.list()

    async def get(self, key: str) -> SkillDefinition:
        skill = await self._repository.get_by_key(key)
        if skill is None:
            raise DefinitionNotFoundError(f"Skill '{key}' not found")
        return skill

    async def find(self, key: str) -> SkillDefinition | None:
        return await self._repository.get_by_key(key)

    async def create(self, skill: SkillDefinition) -> SkillDefinition:
        if await self._repository.get_by_key(skill.key) is not None:
            raise DefinitionAlreadyExistsError(f"Skill '{skill.key}' already exists")
        normalized = skill.model_copy(update={"version": 1})
        return await self._repository.create(normalized)

    async def update(self, key: str, skill: SkillDefinition) -> SkillDefinition:
        if key != skill.key:
            raise InvalidDefinitionReferenceError("Path key must match skill key")
        current = await self._repository.get_by_key(key)
        if current is None:
            raise DefinitionNotFoundError(f"Skill '{key}' not found")
        versioned = skill.model_copy(update={"id": current.id, "version": current.version + 1})
        return await self._repository.update(versioned)


class AgentRegistry:
    """Application service that owns agent definitions and validates skill references."""

    def __init__(self, repository: AgentRepository, skill_repository: SkillRepository) -> None:
        self._repository = repository
        self._skill_repository = skill_repository

    async def list(self) -> list[AgentDefinition]:
        return await self._repository.list()

    async def get(self, key: str) -> AgentDefinition:
        agent = await self._repository.get_by_key(key)
        if agent is None:
            raise DefinitionNotFoundError(f"Agent '{key}' not found")
        return agent

    async def find(self, key: str) -> AgentDefinition | None:
        return await self._repository.get_by_key(key)

    async def create(self, agent: AgentDefinition) -> AgentDefinition:
        if await self._repository.get_by_key(agent.key) is not None:
            raise DefinitionAlreadyExistsError(f"Agent '{agent.key}' already exists")
        await self._validate_skill_references(agent)
        normalized = agent.model_copy(update={"version": 1})
        return await self._repository.create(normalized)

    async def update(self, key: str, agent: AgentDefinition) -> AgentDefinition:
        if key != agent.key:
            raise InvalidDefinitionReferenceError("Path key must match agent key")
        current = await self._repository.get_by_key(key)
        if current is None:
            raise DefinitionNotFoundError(f"Agent '{key}' not found")
        await self._validate_skill_references(agent)
        versioned = agent.model_copy(update={"id": current.id, "version": current.version + 1})
        return await self._repository.update(versioned)

    async def _validate_skill_references(self, agent: AgentDefinition) -> None:
        missing = [
            skill_key
            for skill_key in agent.skills
            if await self._skill_repository.get_by_key(skill_key) is None
        ]
        if missing:
            raise InvalidDefinitionReferenceError(
                f"Unknown skill references: {', '.join(sorted(set(missing)))}"
            )
