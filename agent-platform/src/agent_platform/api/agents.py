from fastapi import APIRouter, HTTPException, Response, status

from agent_platform.api.dependencies import AgentRepositoryDep
from agent_platform.domain import AgentDefinition

router = APIRouter(prefix="/v1/agents", tags=["agents"])


@router.get("", response_model=list[AgentDefinition])
async def list_agents(repository: AgentRepositoryDep) -> list[AgentDefinition]:
    return await repository.list()


@router.get("/{key}", response_model=AgentDefinition)
async def get_agent(key: str, repository: AgentRepositoryDep) -> AgentDefinition:
    agent = await repository.get_by_key(key)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


@router.post("", response_model=AgentDefinition, status_code=status.HTTP_201_CREATED)
async def create_agent(agent: AgentDefinition, response: Response, repository: AgentRepositoryDep) -> AgentDefinition:
    if await repository.get_by_key(agent.key) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent already exists")
    created = await repository.create(agent)
    response.headers["Location"] = f"/v1/agents/{agent.key}"
    return created


@router.put("/{key}", response_model=AgentDefinition)
async def update_agent(key: str, agent: AgentDefinition, repository: AgentRepositoryDep) -> AgentDefinition:
    if key != agent.key:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Path key must match agent key")
    if await repository.get_by_key(key) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return await repository.update(agent)
