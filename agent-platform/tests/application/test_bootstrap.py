from agent_platform.application.registries import AgentRegistry, SkillRegistry
from agent_platform.bootstrap import BootstrapImporter, load_bootstrap_catalog
from agent_platform.domain import AgentDefinition, SkillDefinition


class InMemoryAgentRepository:
    def __init__(self) -> None:
        self.values: dict[str, AgentDefinition] = {}

    async def list(self) -> list[AgentDefinition]:
        return list(self.values.values())

    async def get_by_key(self, key: str) -> AgentDefinition | None:
        return self.values.get(key)

    async def create(self, agent: AgentDefinition) -> AgentDefinition:
        self.values[agent.key] = agent
        return agent

    async def update(self, agent: AgentDefinition) -> AgentDefinition:
        self.values[agent.key] = agent
        return agent


class InMemorySkillRepository:
    def __init__(self) -> None:
        self.values: dict[str, SkillDefinition] = {}

    async def list(self) -> list[SkillDefinition]:
        return list(self.values.values())

    async def get_by_key(self, key: str) -> SkillDefinition | None:
        return self.values.get(key)

    async def create(self, skill: SkillDefinition) -> SkillDefinition:
        self.values[skill.key] = skill
        return skill

    async def update(self, skill: SkillDefinition) -> SkillDefinition:
        self.values[skill.key] = skill
        return skill


def registries() -> tuple[SkillRegistry, AgentRegistry, InMemorySkillRepository, InMemoryAgentRepository]:
    skill_repository = InMemorySkillRepository()
    agent_repository = InMemoryAgentRepository()
    return (
        SkillRegistry(skill_repository),
        AgentRegistry(agent_repository, skill_repository),
        skill_repository,
        agent_repository,
    )


def test_bootstrap_catalog_replicates_current_proposal_copilot_definitions() -> None:
    skills, agents = load_bootstrap_catalog()

    assert {skill.key for skill in skills} == {
        "create-offer",
        "ingest-sources",
        "analyze-opportunity",
        "build-strategy",
        "define-solution",
        "design-proposal",
        "generate-presentation",
    }
    assert {agent.key for agent in agents} == {
        "business-analyst",
        "solution-architect",
        "delivery-manager",
        "presentation-builder",
        "security-specialist",
        "corporate-slide-designer",
    }
    business_analyst = next(agent for agent in agents if agent.key == "business-analyst")
    assert "Business Analyst / Offer Owner" in business_analyst.role
    assert "define-solution" in business_analyst.skills
    define_solution = next(skill for skill in skills if skill.key == "define-solution")
    assert "Fase 3" in define_solution.instructions


async def test_bootstrap_import_is_idempotent_and_preserves_db_edits_by_default() -> None:
    skills, agents, skill_repository, agent_repository = registries()
    importer = BootstrapImporter(skills, agents)

    first = await importer.import_all()
    assert len(first["skills"]["created"]) == 7
    assert len(first["agents"]["created"]) == 6

    original = skill_repository.values["build-strategy"]
    skill_repository.values["build-strategy"] = original.model_copy(update={"description": "Runtime edited description"})

    second = await importer.import_all()
    assert len(second["skills"]["created"]) == 0
    assert "build-strategy" in second["skills"]["skipped"]
    assert skill_repository.values["build-strategy"].description == "Runtime edited description"
    assert len(agent_repository.values) == 6


async def test_bootstrap_sync_updates_changed_definitions_and_versions_them() -> None:
    skills, agents, skill_repository, _ = registries()
    importer = BootstrapImporter(skills, agents)
    await importer.import_all()

    original = skill_repository.values["build-strategy"]
    skill_repository.values["build-strategy"] = original.model_copy(update={"description": "Runtime edited description"})

    report = await importer.import_all(sync=True)

    assert "build-strategy" in report["skills"]["updated"]
    synced = skill_repository.values["build-strategy"]
    assert synced.description != "Runtime edited description"
    assert synced.version == 2
