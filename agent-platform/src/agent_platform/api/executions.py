from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from agent_platform.api.state import agents, executions, skills
from agent_platform.domain import AgentExecution, AgentExecutionRequest

router = APIRouter(prefix="/v1/executions", tags=["executions"])


@router.post("", response_model=AgentExecution, status_code=status.HTTP_202_ACCEPTED)
async def create_execution(request: AgentExecutionRequest) -> AgentExecution:
    if request.agent_key not in agents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    if request.skill_key is not None and request.skill_key not in skills:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")

    execution = AgentExecution(
        correlation_id=request.correlation_id,
        agent_key=request.agent_key,
        skill_key=request.skill_key,
        objective=request.objective,
    )
    executions[execution.id] = execution
    return execution


@router.get("/{execution_id}", response_model=AgentExecution)
async def get_execution(execution_id: UUID) -> AgentExecution:
    execution = executions.get(execution_id)
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    return execution


@router.get("/{execution_id}/events")
async def execution_events(execution_id: UUID) -> StreamingResponse:
    execution = executions.get(execution_id)
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")

    async def stream() -> AsyncIterator[str]:
        # Runtime event history/streaming will replace this initial snapshot in a later block.
        yield f"event: execution\ndata: {execution.model_dump_json()}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
