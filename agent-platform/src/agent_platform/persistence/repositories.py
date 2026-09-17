from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.domain import (
    AgentConstraints,
    AgentDefinition,
    AgentError,
    AgentExecution,
    AgentUsage,
    ExecutionStatus,
    ModelPolicy,
    SkillDefinition,
)
from agent_platform.persistence.models import (
    AgentCapabilityRecord,
    AgentKnowledgeScopeRecord,
    AgentRecord,
    AgentSkillRecord,
    AgentToolRecord,
    ExecutionEventRecord,
    ExecutionRecord,
    SkillRecord,
)


def _agent_to_domain(record: AgentRecord) -> AgentDefinition:
    return AgentDefinition(
        id=record.id,
        key=record.key,
        name=record.name,
        description=record.description,
        role=record.role,
        capabilities=[item.value for item in record.capabilities],
        skills=[item.skill_key for item in record.skills],
        knowledge_scopes=[item.scope_key for item in record.knowledge_scopes],
        allowed_tools=[item.tool_key for item in record.tools],
        model_policy=ModelPolicy.model_validate(record.model_policy or {}),
        constraints=AgentConstraints.model_validate(record.constraints or {}),
        version=record.version,
        enabled=record.enabled,
    )


def _skill_to_domain(record: SkillRecord) -> SkillDefinition:
    return SkillDefinition(
        id=record.id,
        key=record.key,
        name=record.name,
        description=record.description,
        objective=record.objective,
        instructions=record.instructions,
        inputs=record.inputs or [],
        output_schema=record.output_schema or {},
        knowledge_sources=record.knowledge_sources or [],
        allowed_tools=record.allowed_tools or [],
        constraints=record.constraints or {},
        version=record.version,
        enabled=record.enabled,
    )


def _execution_to_domain(record: ExecutionRecord) -> AgentExecution:
    return AgentExecution(
        id=record.id,
        correlation_id=record.correlation_id,
        agent_key=record.agent_key,
        skill_key=record.skill_key,
        status=ExecutionStatus(record.status),
        objective=record.objective,
        runtime=record.runtime,
        model=record.model,
        started_at=record.started_at,
        completed_at=record.completed_at,
        created_at=record.created_at,
        usage=AgentUsage.model_validate(record.usage or {}),
        provider_request_id=record.provider_request_id,
        trace_id=record.trace_id,
        error=AgentError.model_validate(record.error) if record.error else None,
    )


class PostgresAgentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[AgentDefinition]:
        result = await self.session.execute(select(AgentRecord).order_by(AgentRecord.key))
        return [_agent_to_domain(record) for record in result.scalars().unique().all()]

    async def get_by_key(self, key: str) -> AgentDefinition | None:
        result = await self.session.execute(select(AgentRecord).where(AgentRecord.key == key))
        record = result.scalars().unique().one_or_none()
        return _agent_to_domain(record) if record else None

    async def create(self, agent: AgentDefinition) -> AgentDefinition:
        record = AgentRecord(
            id=agent.id,
            key=agent.key,
            name=agent.name,
            description=agent.description,
            role=agent.role,
            model_policy=agent.model_policy.model_dump(mode="json"),
            constraints=agent.constraints.model_dump(mode="json"),
            version=agent.version,
            enabled=agent.enabled,
            capabilities=[AgentCapabilityRecord(value=value) for value in agent.capabilities],
            skills=[AgentSkillRecord(skill_key=value) for value in agent.skills],
            tools=[AgentToolRecord(tool_key=value) for value in agent.allowed_tools],
            knowledge_scopes=[AgentKnowledgeScopeRecord(scope_key=value) for value in agent.knowledge_scopes],
        )
        self.session.add(record)
        await self.session.commit()
        return agent

    async def update(self, agent: AgentDefinition) -> AgentDefinition:
        result = await self.session.execute(select(AgentRecord).where(AgentRecord.key == agent.key))
        record = result.scalars().unique().one()
        record.name = agent.name
        record.description = agent.description
        record.role = agent.role
        record.model_policy = agent.model_policy.model_dump(mode="json")
        record.constraints = agent.constraints.model_dump(mode="json")
        record.version = agent.version
        record.enabled = agent.enabled
        record.capabilities = [AgentCapabilityRecord(value=value) for value in agent.capabilities]
        record.skills = [AgentSkillRecord(skill_key=value) for value in agent.skills]
        record.tools = [AgentToolRecord(tool_key=value) for value in agent.allowed_tools]
        record.knowledge_scopes = [AgentKnowledgeScopeRecord(scope_key=value) for value in agent.knowledge_scopes]
        await self.session.commit()
        return agent


class PostgresSkillRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[SkillDefinition]:
        result = await self.session.execute(select(SkillRecord).order_by(SkillRecord.key))
        return [_skill_to_domain(record) for record in result.scalars().all()]

    async def get_by_key(self, key: str) -> SkillDefinition | None:
        result = await self.session.execute(select(SkillRecord).where(SkillRecord.key == key))
        record = result.scalar_one_or_none()
        return _skill_to_domain(record) if record else None

    async def create(self, skill: SkillDefinition) -> SkillDefinition:
        self.session.add(
            SkillRecord(
                id=skill.id,
                key=skill.key,
                name=skill.name,
                description=skill.description,
                objective=skill.objective,
                instructions=skill.instructions,
                inputs=skill.inputs,
                output_schema=skill.output_schema,
                knowledge_sources=skill.knowledge_sources,
                allowed_tools=skill.allowed_tools,
                constraints=skill.constraints,
                version=skill.version,
                enabled=skill.enabled,
            )
        )
        await self.session.commit()
        return skill

    async def update(self, skill: SkillDefinition) -> SkillDefinition:
        result = await self.session.execute(select(SkillRecord).where(SkillRecord.key == skill.key))
        record = result.scalar_one()
        record.name = skill.name
        record.description = skill.description
        record.objective = skill.objective
        record.instructions = skill.instructions
        record.inputs = skill.inputs
        record.output_schema = skill.output_schema
        record.knowledge_sources = skill.knowledge_sources
        record.allowed_tools = skill.allowed_tools
        record.constraints = skill.constraints
        record.version = skill.version
        record.enabled = skill.enabled
        await self.session.commit()
        return skill


class PostgresExecutionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, execution_id: UUID) -> AgentExecution | None:
        record = await self.session.get(ExecutionRecord, execution_id)
        return _execution_to_domain(record) if record else None

    async def create(self, execution: AgentExecution) -> AgentExecution:
        self.session.add(
            ExecutionRecord(
                id=execution.id,
                correlation_id=execution.correlation_id,
                agent_key=execution.agent_key,
                skill_key=execution.skill_key,
                status=execution.status.value,
                objective=execution.objective,
                runtime=execution.runtime,
                model=execution.model,
                started_at=execution.started_at,
                completed_at=execution.completed_at,
                created_at=execution.created_at,
                usage=execution.usage.model_dump(mode="json"),
                provider_request_id=execution.provider_request_id,
                trace_id=execution.trace_id,
                error=execution.error.model_dump(mode="json") if execution.error else None,
            )
        )
        await self.session.commit()
        return execution

    async def update(self, execution: AgentExecution) -> AgentExecution:
        record = await self.session.get(ExecutionRecord, execution.id)
        if record is None:
            raise LookupError(f"Execution '{execution.id}' not found")
        record.status = execution.status.value
        record.runtime = execution.runtime
        record.model = execution.model
        record.started_at = execution.started_at
        record.completed_at = execution.completed_at
        record.usage = execution.usage.model_dump(mode="json")
        record.provider_request_id = execution.provider_request_id
        record.trace_id = execution.trace_id
        record.error = execution.error.model_dump(mode="json") if execution.error else None
        await self.session.commit()
        return execution

    async def add_event(self, execution_id: UUID, event_type: str, payload: dict) -> None:
        self.session.add(
            ExecutionEventRecord(
                execution_id=execution_id,
                event_type=event_type,
                payload=payload,
                created_at=datetime.now(timezone.utc),
            )
        )
        await self.session.commit()

    async def list_events(self, execution_id: UUID) -> list[dict]:
        result = await self.session.execute(
            select(ExecutionEventRecord)
            .where(ExecutionEventRecord.execution_id == execution_id)
            .order_by(ExecutionEventRecord.created_at)
        )
        return [
            {
                "event_type": record.event_type,
                "payload": record.payload,
                "created_at": record.created_at.isoformat(),
            }
            for record in result.scalars().all()
        ]
