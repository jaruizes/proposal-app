import json
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from agent_platform.api.dependencies import AgentRepositoryDep, ExecutionRepositoryDep, SkillRepositoryDep
from agent_platform.domain import AgentExecution, AgentExecutionRequest

router = APIRouter(prefix="/v1/executions", tags=["executions"])


@router.post("", response_model=AgentExecution, status_code=status.HTTP_202_ACCEPTED)
async def create_execution(
    request: AgentExecutionRequest,
    agents: AgentRepositoryDep,
    skills: SkillRepositoryDep,
    executions: ExecutionRepositoryDep,
) -> AgentExecution:
    if await agents.get_by_key(request.agent_key) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    if request.skill_key is not None and await skills.get_by_key(request.skill_key) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")

    execution = AgentExecution(
        correlation_id=request.correlation_id,
        agent_key=request.agent_key,
        skill_key=request.skill_key,
        objective=request.objective,
    )
    await executions.create(execution)
    await executions.add_event(
        execution.id,
        "execution.queued",
        execution.model_dump(mode="json"),
    )
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
