"""Regression for bootstrapping an agent that already has unique child rows."""
from types import SimpleNamespace

import pytest
from sqlalchemy import ForeignKey, JSON, String, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session

from agent_platform.persistence import repositories


class Base(DeclarativeBase):
    pass


class Agent(Base):
    __tablename__ = "agents"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    model_policy: Mapped[dict] = mapped_column(JSON)
    constraints: Mapped[dict] = mapped_column(JSON)
    version: Mapped[int] = mapped_column()
    enabled: Mapped[bool] = mapped_column()
    capabilities = relationship("Capability", cascade="all, delete-orphan")
    skills = relationship("Skill", cascade="all, delete-orphan")
    tools = relationship("Tool", cascade="all, delete-orphan")
    knowledge_scopes = relationship("Scope", cascade="all, delete-orphan")


class Capability(Base):
    __tablename__ = "agent_capabilities"
    __table_args__ = (UniqueConstraint("agent_id", "value"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))
    value: Mapped[str] = mapped_column(String)


class Skill(Base):
    __tablename__ = "agent_skills"
    __table_args__ = (UniqueConstraint("agent_id", "skill_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))
    skill_key: Mapped[str] = mapped_column(String)


class Tool(Base):
    __tablename__ = "agent_tools"
    __table_args__ = (UniqueConstraint("agent_id", "tool_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))
    tool_key: Mapped[str] = mapped_column(String)


class Scope(Base):
    __tablename__ = "agent_knowledge_scopes"
    __table_args__ = (UniqueConstraint("agent_id", "scope_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))
    scope_key: Mapped[str] = mapped_column(String)


class AsyncSessionAdapter:
    def __init__(self, session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)

    async def commit(self):
        self.session.commit()


@pytest.mark.asyncio
async def test_agent_update_reuses_existing_rows_and_syncs_changes(monkeypatch):
    for name, model in (("AgentRecord", Agent), ("AgentCapabilityRecord", Capability),
                        ("AgentSkillRecord", Skill), ("AgentToolRecord", Tool),
                        ("AgentKnowledgeScopeRecord", Scope)):
        monkeypatch.setattr(repositories, name, model)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            agent = Agent(key="business-analyst", name="BA", description="old", role="Writer",
                          model_policy={}, constraints={}, version=1, enabled=True,
                          capabilities=[Capability(value="opportunity-analysis"), Capability(value="obsolete")],
                          skills=[Skill(skill_key="compose-proposal")], tools=[Tool(tool_key="search")],
                          knowledge_scopes=[Scope(scope_key="offers")])
            session.add(agent)
            session.commit()
            preserved = {
                "capability": next(item.id for item in agent.capabilities if item.value == "opportunity-analysis"),
                "skill": agent.skills[0].id,
                "tool": agent.tools[0].id,
                "scope": agent.knowledge_scopes[0].id,
            }
            empty = SimpleNamespace(model_dump=lambda **_: {})
            desired = SimpleNamespace(key="business-analyst", name="BA", description="new", role="Writer",
                                      model_policy=empty, constraints=empty, version=2, enabled=True,
                                      capabilities=["opportunity-analysis", "proposal-authoring"],
                                      skills=["compose-proposal"], allowed_tools=["search"],
                                      knowledge_scopes=["offers"])
            repository = repositories.PostgresAgentRepository(AsyncSessionAdapter(session))
            await repository.update(desired)
            await repository.update(desired)  # startup --sync must also be safe on subsequent runs
            assert {item.value: item.id for item in agent.capabilities}["opportunity-analysis"] == preserved["capability"]
            assert {item.value for item in agent.capabilities} == {"opportunity-analysis", "proposal-authoring"}
            assert agent.skills[0].id == preserved["skill"]
            assert agent.tools[0].id == preserved["tool"]
            assert agent.knowledge_scopes[0].id == preserved["scope"]
            assert agent.description == "new"
    finally:
        engine.dispose()
