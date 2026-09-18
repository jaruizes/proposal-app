import asyncio,json
from collections.abc import AsyncIterator
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,status
from fastapi.responses import StreamingResponse
from typing import Annotated
from agent_platform.api.dependencies import AgentRuntimeDep,ExecutionRepositoryDep
from agent_platform.application.dispatcher import ExecutionDispatcher,get_execution_dispatcher
from agent_platform.application.registries import DefinitionNotFoundError
from agent_platform.application.runtime import AgentRuntimeValidationError
from agent_platform.domain import AgentExecution,AgentExecutionRequest,ExecutionStatus

router=APIRouter(prefix="/v1/executions",tags=["executions"])
DispatcherDep=Annotated[ExecutionDispatcher,Depends(get_execution_dispatcher)]

@router.post("",response_model=AgentExecution,status_code=status.HTTP_202_ACCEPTED)
async def create_execution(request:AgentExecutionRequest,runtime:AgentRuntimeDep,dispatcher:DispatcherDep)->AgentExecution:
    try:
        execution=await runtime.submit(request);dispatcher.dispatch(execution.id,request);return execution
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
    async def stream()->AsyncIterator[str]:
        sent=0
        while True:
            events=await executions.list_events(execution_id)
            for event in events[sent:]:
                sent+=1;yield f"event: {event['event_type']}\ndata: {json.dumps(event,separators=(',',':'))}\n\n"
            current=await executions.get(execution_id)
            if current is None or current.status in {ExecutionStatus.COMPLETED,ExecutionStatus.FAILED,ExecutionStatus.CANCELLED}:break
            yield ": heartbeat\n\n";await asyncio.sleep(1)
    return StreamingResponse(stream(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@router.get("/{execution_id}/result")
async def execution_result(execution_id:UUID,executions:ExecutionRepositoryDep):
    execution=await executions.get(execution_id)
    if execution is None:raise HTTPException(status_code=404,detail="Execution not found")
    events=await executions.list_events(execution_id)
    result=next((event["payload"] for event in reversed(events) if event["event_type"]=="execution.result"),None)
    if result is not None:return result
    if execution.status is ExecutionStatus.FAILED:return{"execution_id":str(execution.id),"status":execution.status.value,"error":execution.error.model_dump(mode="json") if execution.error else None}
    raise HTTPException(status_code=409,detail=f"Execution is {execution.status.value}")

@router.get("/{execution_id}/diagnostics")
async def execution_diagnostics(execution_id:UUID,executions:ExecutionRepositoryDep)->dict:
    execution=await executions.get(execution_id)
    if execution is None:raise HTTPException(status_code=404,detail="Execution not found")
    events=await executions.list_events(execution_id);safe_events=[]
    for event in events:
        payload=event.get("payload") or {};event_type=event["event_type"]
        if event_type=="execution.result":payload={"status":payload.get("status"),"model":payload.get("model"),"usage":payload.get("usage"),"provider_request_id":payload.get("provider_request_id"),"artifact_count":len(payload.get("artifacts",[]))}
        elif event_type in {"execution.queued","execution.running","execution.completed","execution.failed"}:payload={key:payload.get(key) for key in ("status","agent_key","skill_key","model","usage","provider_request_id","trace_id","error") if key in payload}
        safe_events.append({"event_type":event_type,"created_at":event.get("created_at"),"payload":payload})
    duration_ms=(execution.completed_at-execution.started_at).total_seconds()*1000 if execution.started_at and execution.completed_at else None
    return{"execution_id":str(execution.id),"trace_id":execution.trace_id,"status":execution.status.value,"agent_key":execution.agent_key,"skill_key":execution.skill_key,"model":execution.model,"usage":execution.usage.model_dump(mode="json"),"provider_request_id":execution.provider_request_id,"duration_ms":duration_ms,"events":safe_events}
