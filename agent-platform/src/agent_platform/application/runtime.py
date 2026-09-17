from datetime import datetime, timezone

from agent_platform.application.cognitive import CognitiveContextBuilder
from agent_platform.application.context import AgentPromptAssembler
from agent_platform.application.memory import MemoryService
from agent_platform.application.models import ModelProvider, ModelProviderError
from agent_platform.application.registries import AgentRegistry, DefinitionNotFoundError, SkillRegistry
from agent_platform.application.repositories import ExecutionRepository
from agent_platform.domain import AgentArtifact, AgentError, AgentExecution, AgentExecutionRequest, AgentExecutionResult, AgentUsage, ExecutionStatus


class AgentRuntimeValidationError(RuntimeError): pass


class AgentRuntime:
    def __init__(self,agents:AgentRegistry,skills:SkillRegistry,executions:ExecutionRepository,model_provider:ModelProvider,prompt_assembler:AgentPromptAssembler|None=None,cognitive_context_builder:CognitiveContextBuilder|None=None,memory_service:MemoryService|None=None)->None:
        self._agents=agents; self._skills=skills; self._executions=executions; self._model_provider=model_provider; self._prompt_assembler=prompt_assembler or AgentPromptAssembler(); self._cognitive_context_builder=cognitive_context_builder or CognitiveContextBuilder(); self._memory_service=memory_service

    async def execute(self,request:AgentExecutionRequest)->AgentExecutionResult:
        agent=await self._agents.get(request.agent_key)
        if not agent.enabled: raise AgentRuntimeValidationError("Agent is disabled")
        skill=None
        if request.skill_key is not None:
            skill=await self._skills.get(request.skill_key)
            if not skill.enabled: raise AgentRuntimeValidationError("Skill is disabled")
            if request.skill_key not in agent.skills: raise AgentRuntimeValidationError("Skill is not assigned to agent")
        execution=AgentExecution(correlation_id=request.correlation_id,agent_key=request.agent_key,skill_key=request.skill_key,objective=request.objective)
        await self._executions.create(execution); await self._record(execution,"execution.queued")
        running=execution.model_copy(update={"status":ExecutionStatus.RUNNING,"runtime":"native-python-v1","started_at":datetime.now(timezone.utc)})
        await self._executions.update(running); await self._record(running,"execution.running")
        try:
            cognitive_context=await self._cognitive_context_builder.build(agent,skill,request)
            await self._executions.add_event(running.id,"cognitive.context.built",cognitive_context.summary())
            model_request=self._prompt_assembler.build(agent,skill,request,cognitive_context); model_result=await self._model_provider.generate(model_request)
            usage=AgentUsage(input_tokens=model_result.usage.input_tokens,output_tokens=model_result.usage.output_tokens,cache_read_tokens=model_result.usage.cache_read_tokens,cache_write_tokens=model_result.usage.cache_write_tokens)
            artifact=AgentArtifact(type="AGENT_OUTPUT",content=model_result.content,metadata={"agent_key":agent.key,"agent_version":agent.version,"skill_key":skill.key if skill else None,"skill_version":skill.version if skill else None,"finish_reason":model_result.finish_reason,"cognitive_context":cognitive_context.summary()})
            completed=running.model_copy(update={"status":ExecutionStatus.COMPLETED,"model":model_result.model,"usage":usage,"provider_request_id":model_result.provider_request_id,"completed_at":datetime.now(timezone.utc)})
            await self._executions.update(completed); await self._record(completed,"execution.completed")
            result=AgentExecutionResult(execution_id=completed.id,status=completed.status,artifacts=[artifact],usage=usage,model=model_result.model,provider_request_id=model_result.provider_request_id,trace_id=completed.trace_id)
            await self._executions.add_event(completed.id,"execution.result",result.model_dump(mode="json"))
            if self._memory_service is not None and self._should_auto_capture(skill):
                try:
                    await self._memory_service.capture_execution(correlation_id=request.correlation_id,agent_key=agent.key,skill_key=skill.key if skill else None,execution_id=completed.id,content=model_result.content,model=model_result.model)
                except Exception:
                    pass
            return result
        except ModelProviderError as exc: return await self._fail(running,exc.code,str(exc),retryable=exc.retryable)
        except Exception as exc: return await self._fail(running,"AGENT_RUNTIME_ERROR",str(exc) or type(exc).__name__)

    @staticmethod
    def _should_auto_capture(skill)->bool:
        if skill is None or not isinstance(skill.constraints,dict): return True
        config=skill.constraints.get("memory",{})
        return bool(config.get("auto_capture",True)) if isinstance(config,dict) else True

    async def _fail(self,execution,code,message,*,retryable=False):
        error=AgentError(code=code,message=message,retryable=retryable); failed=execution.model_copy(update={"status":ExecutionStatus.FAILED,"error":error,"completed_at":datetime.now(timezone.utc)})
        await self._executions.update(failed); await self._record(failed,"execution.failed")
        return AgentExecutionResult(execution_id=failed.id,status=failed.status,usage=failed.usage,model=failed.model,provider_request_id=failed.provider_request_id,trace_id=failed.trace_id,error=error)

    async def _record(self,execution,event_type): await self._executions.add_event(execution.id,event_type,execution.model_dump(mode="json"))


__all__=["AgentRuntime","AgentRuntimeValidationError","DefinitionNotFoundError"]
