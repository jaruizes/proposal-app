from fastapi import APIRouter, HTTPException, Response, status

from agent_platform.api.dependencies import AgentRegistryDep
from agent_platform.application.registries import (
    DefinitionAlreadyExistsError,
    DefinitionNotFoundError,
    InvalidDefinitionReferenceError,
)
from agent_platform.domain import AgentDefinition

router = APIRouter(prefix="/v1/agents", tags=["agents"])


@router.get("", response_model=list[AgentDefinition])
async def list_agents(registry: AgentRegistryDep) -> list[AgentDefinition]:
    return await registry.list()


@router.get("/{key}", response_model=AgentDefinition)
async def get_agent(key: str, registry: AgentRegistryDep) -> AgentDefinition:
    try:
        return await registry.get(key)
    except DefinitionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("", response_model=AgentDefinition, status_code=status.HTTP_201_CREATED)
async def create_agent(agent: AgentDefinition, response: Response, registry: AgentRegistryDep) -> AgentDefinition:
    try:
        created = await registry.create(agent)
    except DefinitionAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidDefinitionReferenceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    response.headers["Location"] = f"/v1/agents/{created.key}"
    return created


@router.put("/{key}", response_model=AgentDefinition)
async def update_agent(key: str, agent: AgentDefinition, registry: AgentRegistryDep) -> AgentDefinition:
    try:
        return await registry.update(key, agent)
    except DefinitionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidDefinitionReferenceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
