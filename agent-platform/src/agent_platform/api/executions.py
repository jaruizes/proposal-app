import json
from collections.abc import AsyncIterator
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter,HTTPException,status
from fastapi.responses import StreamingResponse

from agent_platform.api.dependencies import AgentRuntimeDep,ExecutionRepositoryDep
from agent_platform.application.registries import DefinitionNotFoundError
from agent_platform.application.runtime import AgentRuntimeValidationError
from agent_platform.domain import AgentExecution,AgentExecutionRequest,AgentExecutionResult

router=APIRouter(prefix="/v1/executions",tags=["executions"])


@router.post("",response_model=AgentExecutionResult,status_code=status.HTTP_200_OK)
async def create_execution(request:AgentExecutionRequest,runtime:AgentRuntimeDep)->AgentExecutionResult:
    try:return await runtime.execute(request)
    except DefinitionNotFoundError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc
    except AgentRuntimeValidationError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc


@router.get("/{execution_id}",response_model=AgentExecution)
async def get_execution(execution_id:UUID,executions:ExecutionRepositoryDep)->AgentExecution:
    execution=await executions.get(execution_id)
    if execution is None:raise HTTPException(status_code=404,detail="Execution not found")
    return execution


@router.get("/{execution_id}/events")
async def execution_events(execution_id:UUID,executions:ExecutionRepositoryDep)->StreamingResponse:
    execution=await executions.get(execution_id)
    if execution is None:raise HTTPException(status_code=404,detail="Execution not found")
    events=await executions.list_events(execution_id)
    async def stream()->AsyncIterator[str]:
        for event in events:yield f"event: {event['event_type']}\ndata: {json.dumps(event,separators=(',',':'))}\n\n"
    return StreamingResponse(stream(),media_type="text/event-stream")


@router.get("/{execution_id}/diagnostics")
async def execution_diagnostics(execution_id:UUID,executions:ExecutionRepositoryDep)->dict:
    execution=await executions.get(execution_id)
    if execution is None:raise HTTPException(status_code=404,detail="Execution not found")
    events=await executions.list_events(execution_id)
    safe_events=[]
    for event in events:
        payload=event.get("payload") or {};event_type=event["event_type"]
        if event_type=="execution.result":
            payload={"status":payload.get("status"),"model":payload.get("model"),"usage":payload.get("usage"),"provider_request_id":payload.get("provider_request_id"),"artifact_count":len(payload.get("artifacts",[]))}
        elif event_type in {"execution.queued","execution.running","execution.completed","execution.failed"}:
            payload={key:payload.get(key) for key in ("status","agent_key","skill_key","model","usage","provider_request_id","trace_id","error") if key in payload}
        safe_events.append({"event_type":event_type,"created_at":event.get("created_at"),"payload":payload})
    duration_ms=None
    if execution.started_at and execution.completed_at:duration_ms=(execution.completed_at-execution.started_at).total_seconds()*1000
    return{"execution_id":str(execution.id),"trace_id":execution.trace_id,"status":execution.status.value,"agent_key":execution.agent_key,"skill_key":execution.skill_key,"model":execution.model,"usage":execution.usage.model_dump(mode="json"),"provider_request_id":execution.provider_request_id,"duration_ms":duration_ms,"events":safe_events}
