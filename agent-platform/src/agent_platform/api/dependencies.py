from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.application.repositories import AgentRepository, ExecutionRepository, SkillRepository
from agent_platform.persistence.database import get_session
from agent_platform.persistence.repositories import (
    PostgresAgentRepository,
    PostgresExecutionRepository,
    PostgresSkillRepository,
)


async def get_agent_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> AgentRepository:
    return PostgresAgentRepository(session)


async def get_skill_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> SkillRepository:
    return PostgresSkillRepository(session)


async def get_execution_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> ExecutionRepository:
    return PostgresExecutionRepository(session)


AgentRepositoryDep = Annotated[AgentRepository, Depends(get_agent_repository)]
SkillRepositoryDep = Annotated[SkillRepository, Depends(get_skill_repository)]
ExecutionRepositoryDep = Annotated[ExecutionRepository, Depends(get_execution_repository)]
