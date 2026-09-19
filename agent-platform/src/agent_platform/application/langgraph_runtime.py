from __future__ import annotations

import time
from typing import TypedDict

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph

from agent_platform.application.models import ModelProviderError, ModelRequest, ModelResult, ModelUsage
from agent_platform.application.observability import EXECUTIONS, EXECUTION_LATENCY, TOKENS, timed_span
from agent_platform.application.runtime import AgentRuntime
from agent_platform.domain import AgentArtifact, AgentExecutionRequest, AgentExecutionResult, AgentUsage, CognitiveContext, ExecutionStatus


class LangGraphState(TypedDict, total=False):
    request: dict
    cognitive_context: dict
    model_request: dict
    model_result: dict
    cache_hit: bool
    cache_key: str | None
    proposal_sections: list[dict]
    proposal_drafts: dict[str, str]
    proposal_content: str


class LangGraphAgentRuntime(AgentRuntime):
    """LangGraph-backed runtime adapter behind the platform's stable execution contract.

    The Agent Platform remains responsible for persistence, cognitive context,
    knowledge, memory, tools and provider abstraction. LangGraph owns the
    internal cognitive execution graph and checkpointing.
    """

    def __init__(self, *args, checkpointer=None, checkpoint_database_url: str | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._external_checkpointer = checkpointer
        self._checkpoint_database_url = checkpoint_database_url

    async def run(self, execution, request):
        started = time.perf_counter()
        skill_label = request.skill_key or "-"
        running = execution.model_copy(
            update={
                "status": ExecutionStatus.RUNNING,
                "runtime": "langgraph-v1",
                "started_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            }
        )
        await self._executions.update(running)
        await self._record(running, "execution.running")
        await self._executions.add_event(running.id, "langgraph.execution.started", {"thread_id": str(running.id)})

        try:
            if self._external_checkpointer is not None:
                final_state = await self._invoke_graph(running, request, self._external_checkpointer)
            else:
                if not self._checkpoint_database_url:
                    raise RuntimeError("LANGGRAPH_CHECKPOINT_DATABASE_URL is required for LangGraph runtime")
                async with AsyncPostgresSaver.from_conn_string(self._checkpoint_database_url) as checkpointer:
                    await checkpointer.setup()
                    final_state = await self._invoke_graph(running, request, checkpointer)

            model_result = ModelResult.model_validate(final_state["model_result"])
            cache_hit = bool(final_state.get("cache_hit", False))
            cognitive_context = CognitiveContext.model_validate(final_state["cognitive_context"])
            agent = await self._agents.get(request.agent_key)
            skill = await self._skills.get(request.skill_key) if request.skill_key else None

            usage = AgentUsage(
                input_tokens=model_result.usage.input_tokens,
                output_tokens=model_result.usage.output_tokens,
                cache_read_tokens=model_result.usage.cache_read_tokens,
                cache_write_tokens=model_result.usage.cache_write_tokens,
            )
            for token_type, value in (
                ("input", usage.input_tokens),
                ("output", usage.output_tokens),
                ("cache_read", usage.cache_read_tokens),
                ("cache_write", usage.cache_write_tokens),
            ):
                if value:
                    TOKENS.labels(agent.key, skill_label, token_type).inc(value)

            artifact = AgentArtifact(
                type="AGENT_OUTPUT",
                content=model_result.content,
                metadata={
                    "agent_key": agent.key,
                    "agent_version": agent.version,
                    "skill_key": skill.key if skill else None,
                    "skill_version": skill.version if skill else None,
                    "finish_reason": model_result.finish_reason,
                    "cognitive_context": cognitive_context.summary(),
                    "platform_cache_hit": cache_hit,
                    "trace_id": running.trace_id,
                    "runtime": "langgraph-v1",
                    "langgraph_thread_id": str(running.id),
                },
            )
            completed = running.model_copy(
                update={
                    "status": ExecutionStatus.COMPLETED,
                    "model": model_result.model,
                    "usage": usage,
                    "provider_request_id": model_result.provider_request_id,
                    "completed_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                }
            )
            await self._executions.update(completed)
            await self._record(completed, "execution.completed")
            result = AgentExecutionResult(
                execution_id=completed.id,
                status=completed.status,
                artifacts=[artifact],
                usage=usage,
                model=model_result.model,
                provider_request_id=model_result.provider_request_id,
                trace_id=completed.trace_id,
            )
            await self._executions.add_event(completed.id, "langgraph.execution.completed", {"thread_id": str(completed.id)})
            await self._executions.add_event(completed.id, "execution.result", result.model_dump(mode="json"))

            if self._memory_service is not None and self._should_auto_capture(skill):
                try:
                    with timed_span("memory.capture"):
                        await self._memory_service.capture_execution(
                            correlation_id=request.correlation_id,
                            agent_key=agent.key,
                            skill_key=skill.key if skill else None,
                            execution_id=completed.id,
                            content=model_result.content,
                            model=model_result.model,
                        )
                except Exception:
                    pass

            EXECUTIONS.labels(agent.key, skill_label, "completed").inc()
            EXECUTION_LATENCY.labels(agent.key, skill_label).observe(time.perf_counter() - started)
            return result
        except ModelProviderError as exc:
            EXECUTIONS.labels(request.agent_key, skill_label, "failed").inc()
            EXECUTION_LATENCY.labels(request.agent_key, skill_label).observe(time.perf_counter() - started)
            return await self._fail(running, exc.code, str(exc), retryable=exc.retryable)
        except Exception as exc:
            EXECUTIONS.labels(request.agent_key, skill_label, "failed").inc()
            EXECUTION_LATENCY.labels(request.agent_key, skill_label).observe(time.perf_counter() - started)
            return await self._fail(running, "LANGGRAPH_RUNTIME_ERROR", str(exc) or type(exc).__name__)

    async def _invoke_graph(self, execution, request: AgentExecutionRequest, checkpointer):
        graph = self._build_graph(execution)
        compiled = graph.compile(checkpointer=checkpointer, name="agent-platform-execution")
        config = {"configurable": {"thread_id": str(execution.id)}}
        initial: LangGraphState = {"request": request.model_dump(mode="json")}
        return await compiled.ainvoke(initial, config=config)

    def _build_graph(self, execution):
        async def build_context(state: LangGraphState):
            request = AgentExecutionRequest.model_validate(state["request"])
            agent = await self._agents.get(request.agent_key)
            skill = await self._skills.get(request.skill_key) if request.skill_key else None
            with timed_span("langgraph.context"):
                cognitive_context = await self._cognitive_context_builder.build(agent, skill, request)
            await self._executions.add_event(execution.id, "cognitive.context.built", cognitive_context.summary())
            await self._executions.add_event(execution.id, "langgraph.node.context.completed", {"items": len(cognitive_context.items)})
            return {"cognitive_context": cognitive_context.model_dump(mode="json")}

        async def invoke_model(state: LangGraphState):
            request = AgentExecutionRequest.model_validate(state["request"])
            cognitive_context = CognitiveContext.model_validate(state["cognitive_context"])
            agent = await self._agents.get(request.agent_key)
            skill = await self._skills.get(request.skill_key) if request.skill_key else None
            model_request = self._prompt_assembler.build(agent, skill, request, cognitive_context)
            cache_config = self._execution_cache_config(skill)
            cache_hit = False
            model_result = None
            cache_key = None

            if self._cache is not None and cache_config["enabled"]:
                from agent_platform.application.cache import stable_cache_key

                cache_key = stable_cache_key(
                    {
                        "agent": [agent.key, agent.version],
                        "skill": [skill.key, skill.version] if skill else None,
                        "model_request": model_request.model_dump(mode="json"),
                    }
                )
                cached = await self._cache.get_json("execution", cache_key)
                if cached is not None:
                    model_result = ModelResult.model_validate(cached).model_copy(
                        update={"usage": ModelUsage(), "provider_request_id": None, "metadata": {"platform_cache_hit": True}}
                    )
                    cache_hit = True
                    await self._executions.add_event(execution.id, "execution.cache.hit", {"key": cache_key})
                else:
                    await self._executions.add_event(execution.id, "execution.cache.miss", {"key": cache_key})

            if model_result is None:
                with timed_span("langgraph.model", model=model_request.model or "default"):
                    model_result = await self._model_provider.generate(model_request)
                if self._cache is not None and cache_config["enabled"] and cache_key:
                    await self._cache.set_json(
                        "execution",
                        cache_key,
                        model_result.model_dump(mode="json"),
                        ttl_seconds=cache_config["ttl_seconds"],
                    )

            await self._executions.add_event(
                execution.id,
                "langgraph.node.model.completed",
                {
                    "model": model_result.model,
                    "provider_request_id": model_result.provider_request_id,
                    "cache_hit": cache_hit,
                },
            )
            return {
                "model_request": model_request.model_dump(mode="json"),
                "model_result": model_result.model_dump(mode="json"),
                "cache_hit": cache_hit,
                "cache_key": cache_key,
            }

        builder = StateGraph(LangGraphState)
        builder.add_node("build_context", build_context)
        builder.add_node("invoke_model", invoke_model)
        builder.add_edge(START, "build_context")
        if execution.skill_key == "compose-proposal":
            from agent_platform.application.proposal_graph import add_proposal_nodes
            add_proposal_nodes(builder, self, execution)
        else:
            builder.add_edge("build_context", "invoke_model")
            builder.add_edge("invoke_model", END)
        return builder


__all__ = ["LangGraphAgentRuntime", "LangGraphState"]
