from fastapi import APIRouter, HTTPException, Response, status

from agent_platform.api.state import agents
from agent_platform.domain import AgentDefinition

router = APIRouter(prefix="/v1/agents", tags=["agents"])


@router.get("", response_model=list[AgentDefinition])
async def list_agents() -> list[AgentDefinition]:
    return list(agents.values())


@router.get("/{key}", response_model=AgentDefinition)
async def get_agent(key: str) -> AgentDefinition:
    agent = agents.get(key)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


@router.post("", response_model=AgentDefinition, status_code=status.HTTP_201_CREATED)
async def create_agent(agent: AgentDefinition, response: Response) -> AgentDefinition:
    if agent.key in agents:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent already exists")
    agents[agent.key] = agent
    response.headers["Location"] = f"/v1/agents/{agent.key}"
    return agent


@router.put("/{key}", response_model=AgentDefinition)
async def update_agent(key: str, agent: AgentDefinition) -> AgentDefinition:
    if key != agent.key:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Path key must match agent key")
    if key not in agents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    agents[key] = agent
    return agent
