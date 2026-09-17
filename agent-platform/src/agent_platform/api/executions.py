import json
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from agent_platform.api.dependencies import AgentRuntimeDep, ExecutionRepositoryDep
from agent_platform.application.registries import DefinitionNotFoundError
from agent_platform.application.runtime import AgentRuntimeValidationError
from agent_platform.domain import AgentExecution, AgentExecutionRequest, AgentExecutionResult

router = APIRouter(prefix="/v1/executions", tags=["executions"])


@router.post("", response_model=AgentExecutionResult, status_code=status.HTTP_200_OK)
async def create_execution(request: AgentExecutionRequest, runtime: AgentRuntimeDep) -> AgentExecutionResult:
    try:
        return await runtime.execute(request)
    except DefinitionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AgentRuntimeValidationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


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
