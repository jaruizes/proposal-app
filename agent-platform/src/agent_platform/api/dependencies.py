from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.application.models import ModelProvider
from agent_platform.application.registries import AgentRegistry, SkillRegistry
from agent_platform.application.repositories import AgentRepository, ExecutionRepository, SkillRepository
from agent_platform.application.runtime import AgentRuntime
from agent_platform.application.tools import ToolRegistry
from agent_platform.config import get_settings
from agent_platform.persistence.database import get_session
from agent_platform.persistence.repositories import (
    PostgresAgentRepository,
    PostgresExecutionRepository,
    PostgresSkillRepository,
)
from agent_platform.providers import AnthropicModelProvider, McpRegistry, McpServerDefinition


async def get_agent_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> AgentRepository:
    return PostgresAgentRepository(session)


async def get_skill_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> SkillRepository:
    return PostgresSkillRepository(session)


async def get_execution_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> ExecutionRepository:
    return PostgresExecutionRepository(session)


AgentRepositoryDep = Annotated[AgentRepository, Depends(get_agent_repository)]
SkillRepositoryDep = Annotated[SkillRepository, Depends(get_skill_repository)]
ExecutionRepositoryDep = Annotated[ExecutionRepository, Depends(get_execution_repository)]


async def get_skill_registry(repository: SkillRepositoryDep) -> SkillRegistry:
    return SkillRegistry(repository)


async def get_agent_registry(repository: AgentRepositoryDep, skills: SkillRepositoryDep) -> AgentRegistry:
    return AgentRegistry(repository, skills)


SkillRegistryDep = Annotated[SkillRegistry, Depends(get_skill_registry)]
AgentRegistryDep = Annotated[AgentRegistry, Depends(get_agent_registry)]


def get_model_provider() -> ModelProvider:
    return AnthropicModelProvider()


ModelProviderDep = Annotated[ModelProvider, Depends(get_model_provider)]


def get_agent_runtime(
    agents: AgentRegistryDep,
    skills: SkillRegistryDep,
    executions: ExecutionRepositoryDep,
    model_provider: ModelProviderDep,
) -> AgentRuntime:
    return AgentRuntime(agents, skills, executions, model_provider)


AgentRuntimeDep = Annotated[AgentRuntime, Depends(get_agent_runtime)]


@lru_cache
def get_mcp_registry() -> McpRegistry:
    settings = get_settings()
    registry = McpRegistry()
    if settings.google_workspace_mcp_enabled:
        env: dict[str, str] = {}
        if settings.google_oauth_credentials:
            env["GOOGLE_OAUTH_CREDENTIALS"] = settings.google_oauth_credentials
        if settings.google_oauth_token:
            env["GOOGLE_OAUTH_TOKEN"] = settings.google_oauth_token
        registry.register(
            McpServerDefinition(
                key="google-workspace",
                command=settings.google_workspace_mcp_command,
                args=(settings.google_workspace_mcp_script,),
                cwd=settings.google_workspace_mcp_cwd,
                env=env,
                timeout_seconds=settings.google_workspace_mcp_timeout_seconds,
            )
        )
    return registry


@lru_cache
def get_tool_registry() -> ToolRegistry:
    return ToolRegistry(get_mcp_registry().tool_providers())


McpRegistryDep = Annotated[McpRegistry, Depends(get_mcp_registry)]
ToolRegistryDep = Annotated[ToolRegistry, Depends(get_tool_registry)]
