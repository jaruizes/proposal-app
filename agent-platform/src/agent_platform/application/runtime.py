from datetime import datetime,timezone
import time

from agent_platform.application.cache import CacheService,stable_cache_key
from agent_platform.application.cognitive import CognitiveContextBuilder
from agent_platform.application.context import AgentPromptAssembler
from agent_platform.application.memory import MemoryService
from agent_platform.application.models import ModelProvider,ModelProviderError,ModelResult,ModelUsage
from agent_platform.application.observability import EXECUTIONS,EXECUTION_LATENCY,TOKENS,timed_span,trace_id_or_new
from agent_platform.application.output_contract import normalize_output,output_media_type
from agent_platform.application.registries import AgentRegistry,DefinitionNotFoundError,SkillRegistry
from agent_platform.application.repositories import ExecutionRepository
from agent_platform.domain import AgentArtifact,AgentError,AgentExecution,AgentExecutionRequest,AgentExecutionResult,AgentUsage,ExecutionStatus

class AgentRuntimeValidationError(RuntimeError):pass

class AgentRuntime:
    def __init__(self,agents,skills,executions,model_provider,prompt_assembler=None,cognitive_context_builder=None,memory_service=None,cache=None)->None:
        self._agents=agents;self._skills=skills;self._executions=executions;self._model_provider=model_provider
        self._prompt_assembler=prompt_assembler or AgentPromptAssembler();self._cognitive_context_builder=cognitive_context_builder or CognitiveContextBuilder()
        self._memory_service=memory_service;self._cache=cache

    async def submit(self,request):
        agent=await self._agents.get(request.agent_key)
        if not agent.enabled:raise AgentRuntimeValidationError("Agent is disabled")
        if request.skill_key is not None:
            skill=await self._skills.get(request.skill_key)
            if not skill.enabled:raise AgentRuntimeValidationError("Skill is disabled")
            if request.skill_key not in agent.skills:raise AgentRuntimeValidationError("Skill is not assigned to agent")
        if request.execution_id is not None:
            existing=await self._executions.get(request.execution_id)
            if existing is not None:return existing
        execution=AgentExecution(id=request.execution_id or __import__("uuid").uuid4(),correlation_id=request.correlation_id,agent_key=request.agent_key,skill_key=request.skill_key,objective=request.objective,trace_id=trace_id_or_new())
        await self._executions.create(execution);await self._record(execution,"execution.queued")
        return execution

    async def execute(self,request):
        execution=await self.submit(request)
        if execution.status in {ExecutionStatus.COMPLETED,ExecutionStatus.FAILED,ExecutionStatus.CANCELLED}:return execution
        return await self.run(execution,request)

    async def run(self,execution,request):
        started=time.perf_counter();skill_label=request.skill_key or "-"
        with timed_span("agent.execution",agent=request.agent_key,skill=skill_label,correlation_id=str(request.correlation_id) if request.correlation_id else None):
            agent=await self._agents.get(request.agent_key);skill=None
            if request.skill_key is not None:skill=await self._skills.get(request.skill_key)
            running=execution.model_copy(update={"status":ExecutionStatus.RUNNING,"runtime":"native-python-v1","started_at":datetime.now(timezone.utc)})
            await self._executions.update(running);await self._record(running,"execution.running")
            try:
                with timed_span("cognitive.context.build"):
                    cognitive_context=await self._cognitive_context_builder.build(agent,skill,request)
                await self._executions.add_event(running.id,"cognitive.context.built",cognitive_context.summary())
                model_request=self._prompt_assembler.build(agent,skill,request,cognitive_context)
                cache_config=self._execution_cache_config(skill);cache_hit=False;model_result=None;cache_key=None
                if self._cache is not None and cache_config["enabled"]:
                    cache_key=stable_cache_key({"agent":[agent.key,agent.version],"skill":[skill.key,skill.version] if skill else None,"model_request":model_request.model_dump(mode="json")})
                    cached=await self._cache.get_json("execution",cache_key)
                    if cached is not None:
                        model_result=ModelResult.model_validate(cached).model_copy(update={"usage":ModelUsage(),"provider_request_id":None,"metadata":{"platform_cache_hit":True}})
                        cache_hit=True;await self._executions.add_event(running.id,"execution.cache.hit",{"key":cache_key})
                    else:await self._executions.add_event(running.id,"execution.cache.miss",{"key":cache_key})
                if model_result is None:
                    with timed_span("model.generate",model=model_request.model or "default"):model_result=await self._model_provider.generate(model_request)
                model_result=model_result.model_copy(update={"content":normalize_output(request,model_result.content)})
                if not cache_hit and self._cache is not None and cache_config["enabled"] and cache_key:
                    await self._cache.set_json("execution",cache_key,model_result.model_dump(mode="json"),ttl_seconds=cache_config["ttl_seconds"])
                usage=AgentUsage(input_tokens=model_result.usage.input_tokens,output_tokens=model_result.usage.output_tokens,cache_read_tokens=model_result.usage.cache_read_tokens,cache_write_tokens=model_result.usage.cache_write_tokens)
                for token_type,value in (("input",usage.input_tokens),("output",usage.output_tokens),("cache_read",usage.cache_read_tokens),("cache_write",usage.cache_write_tokens)):
                    if value:TOKENS.labels(agent.key,skill_label,token_type).inc(value)
                artifact=AgentArtifact(type="AGENT_OUTPUT",content=model_result.content,media_type=output_media_type(request,model_result.content),metadata={"agent_key":agent.key,"agent_version":agent.version,"skill_key":skill.key if skill else None,"skill_version":skill.version if skill else None,"finish_reason":model_result.finish_reason,"cognitive_context":cognitive_context.summary(),"platform_cache_hit":cache_hit,"trace_id":running.trace_id})
                completed=running.model_copy(update={"status":ExecutionStatus.COMPLETED,"model":model_result.model,"usage":usage,"provider_request_id":model_result.provider_request_id,"completed_at":datetime.now(timezone.utc)})
                await self._executions.update(completed);await self._record(completed,"execution.completed")
                result=AgentExecutionResult(execution_id=completed.id,status=completed.status,artifacts=[artifact],usage=usage,model=model_result.model,provider_request_id=model_result.provider_request_id,trace_id=completed.trace_id)
                await self._executions.add_event(completed.id,"execution.result",result.model_dump(mode="json"))
                if self._memory_service is not None and self._should_auto_capture(skill):
                    try:
                        with timed_span("memory.capture"):await self._memory_service.capture_execution(correlation_id=request.correlation_id,agent_key=agent.key,skill_key=skill.key if skill else None,execution_id=completed.id,content=model_result.content,model=model_result.model)
                    except Exception:pass
                EXECUTIONS.labels(agent.key,skill_label,"completed").inc();EXECUTION_LATENCY.labels(agent.key,skill_label).observe(time.perf_counter()-started)
                return result
            except ModelProviderError as exc:
                EXECUTIONS.labels(agent.key,skill_label,"failed").inc();EXECUTION_LATENCY.labels(agent.key,skill_label).observe(time.perf_counter()-started);return await self._fail(running,exc.code,str(exc),retryable=exc.retryable)
            except Exception as exc:
                EXECUTIONS.labels(agent.key,skill_label,"failed").inc();EXECUTION_LATENCY.labels(agent.key,skill_label).observe(time.perf_counter()-started);return await self._fail(running,"AGENT_RUNTIME_ERROR",str(exc) or type(exc).__name__)

    @staticmethod
    def _execution_cache_config(skill):
        if skill is None or not isinstance(skill.constraints,dict):return{"enabled":False,"ttl_seconds":900}
        cache=skill.constraints.get("cache",{});execution=cache.get("execution",{}) if isinstance(cache,dict) else {};return{"enabled":bool(execution.get("enabled",False)),"ttl_seconds":max(1,int(execution.get("ttl_seconds",900)))}
    @staticmethod
    def _should_auto_capture(skill):
        if skill is None or not isinstance(skill.constraints,dict):return True
        config=skill.constraints.get("memory",{});return bool(config.get("auto_capture",True)) if isinstance(config,dict) else True
    async def _fail(self,execution,code,message,*,retryable=False):
        error=AgentError(code=code,message=message,retryable=retryable);failed=execution.model_copy(update={"status":ExecutionStatus.FAILED,"error":error,"completed_at":datetime.now(timezone.utc)})
        await self._executions.update(failed);await self._record(failed,"execution.failed");return AgentExecutionResult(execution_id=failed.id,status=failed.status,usage=failed.usage,model=failed.model,provider_request_id=failed.provider_request_id,trace_id=failed.trace_id,error=error)
    async def _record(self,execution,event_type):await self._executions.add_event(execution.id,event_type,execution.model_dump(mode="json"))

__all__=["AgentRuntime","AgentRuntimeValidationError","DefinitionNotFoundError"]
