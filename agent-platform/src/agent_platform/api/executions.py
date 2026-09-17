import json
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from agent_platform.api.dependencies import AgentRegistryDep, ExecutionRepositoryDep, SkillRegistryDep
from agent_platform.application.registries import DefinitionNotFoundError
from agent_platform.domain import AgentExecution, AgentExecutionRequest

router = APIRouter(prefix="/v1/executions", tags=["executions"])


@router.post("", response_model=AgentExecution, status_code=status.HTTP_202_ACCEPTED)
async def create_execution(
    request: AgentExecutionRequest,
    agents: AgentRegistryDep,
    skills: SkillRegistryDep,
    executions: ExecutionRepositoryDep,
) -> AgentExecution:
    try:
        agent = await agents.get(request.agent_key)
    except DefinitionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if not agent.enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent is disabled")

    if request.skill_key is not None:
        try:
            skill = await skills.get(request.skill_key)
        except DefinitionNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        if not skill.enabled:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Skill is disabled")
        if request.skill_key not in agent.skills:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Skill is not assigned to agent")

    execution = AgentExecution(
        correlation_id=request.correlation_id,
        agent_key=request.agent_key,
        skill_key=request.skill_key,
        objective=request.objective,
    )
    await executions.create(execution)
    await executions.add_event(execution.id, "execution", execution.model_dump(mode="json"))
    return execution


@router.get("/{execution_id}", response_model=AgentExecution)
async def get_execution(execution_id: UUID, executions: ExecutionRepositoryDep) -> AgentExecution:
    execution = await executions.get(execution_id)
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    return execution


@router.get("/{execution_id}/events")
async def execution_events(execution_id: UUID, executions: ExecutionRepositoryDep) -> StreamingResponse:
    execution = await executions.get(execution_id)
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    events = await executions.list_events(execution_id)

    async def stream() -> AsyncIterator[str]:
        for event in events:
            yield f"event: {event['event_type']}\ndata: {json.dumps(event, separators=(',', ':'))}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
