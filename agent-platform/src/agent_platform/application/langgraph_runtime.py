from __future__ import annotations

import time
from typing import TypedDict

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph

from agent_platform.application.graph_registry import GraphRegistry
from agent_platform.application.models import ModelMessage, ModelProviderError, ModelRequest, ModelResult, ModelRole, ModelUsage
from agent_platform.application.observability import EXECUTIONS, EXECUTION_LATENCY, TOKENS, timed_span
from agent_platform.application.output_contract import normalize_output, output_media_type
from agent_platform.application.runtime import AgentRuntime
from agent_platform.config import get_settings
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
    proposal_force_split: bool
    proposal_references: dict[str, list[dict]]
    proposal_context_pack: dict
    proposal_quality_degraded: bool
    proposal_skipped_quality_steps: list[str]
    presentation_plan_mode: str
    presentation_plan_force_split: bool
    presentation_plan_title: str
    presentation_plan_sections: list[dict]


class LangGraphAgentRuntime(AgentRuntime):
    """LangGraph-backed runtime adapter behind the platform's stable execution contract.

    The Agent Platform remains responsible for persistence, cognitive context,
    knowledge, memory, tools and provider abstraction. LangGraph owns the
    internal cognitive execution graph and checkpointing.
    """

    def __init__(self, *args, checkpointer=None, checkpoint_database_url: str | None = None, proposal_retrieval_service=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._external_checkpointer = checkpointer
        self._checkpoint_database_url = checkpoint_database_url
        self._proposal_retrieval_service = proposal_retrieval_service

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
            model_result = model_result.model_copy(update={"content": normalize_output(request, model_result.content)})
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

            pricing = get_settings()
            estimated_cost_usd = (
                usage.input_tokens * pricing.anthropic_input_cost_per_million_usd
                + usage.output_tokens * pricing.anthropic_output_cost_per_million_usd
                + usage.cache_read_tokens * pricing.anthropic_cache_read_cost_per_million_usd
                + usage.cache_write_tokens * pricing.anthropic_cache_write_cost_per_million_usd
            ) / 1_000_000.0
            execution_usage_metadata = {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "cache_read_tokens": usage.cache_read_tokens,
                "cache_write_tokens": usage.cache_write_tokens,
                "estimated_cost_usd": round(estimated_cost_usd, 6),
            }

            artifact = AgentArtifact(
                type="AGENT_OUTPUT",
                content=model_result.content,
                media_type=output_media_type(request, model_result.content),
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
                    "model_metadata": {
                        **model_result.metadata,
                        "execution_usage": execution_usage_metadata,
                    },
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
        skill = await self._skills.get(request.skill_key) if request.skill_key else None
        graph = self._build_graph(execution, skill)
        compiled = graph.compile(checkpointer=checkpointer, name="agent-platform-execution")
        config = {"configurable": {"thread_id": str(execution.id)}}
        initial: LangGraphState = {"request": request.model_dump(mode="json")}
        return await compiled.ainvoke(initial, config=config)

    def _build_graph(self, execution, skill_definition=None):
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
                execution_policy = skill.constraints.get("execution", {}) if skill and isinstance(skill.constraints, dict) else {}
                truncation = execution_policy.get("truncation", {}) if isinstance(execution_policy, dict) else {}
                max_attempts = max(1, int(truncation.get("max_attempts", 3)))
                factors = truncation.get("shrink_factors", [1.0, 0.65, 0.40])
                if not isinstance(factors, list) or not factors:
                    factors = [1.0, 0.65, 0.40]
                min_output_tokens = max(256, int(truncation.get("min_output_tokens", 700)))
                base_max = model_request.max_output_tokens or 16000

                last_retry_code = None
                for attempt in range(max_attempts):
                    factor = float(factors[min(attempt, len(factors) - 1)])
                    attempt_max = max(min_output_tokens, int(base_max * factor))
                    if attempt == 0:
                        attempt_request = model_request.model_copy(update={"max_output_tokens": attempt_max})
                    else:
                        format_name = str(request.constraints.get("output_format", "text"))
                        contract_hint = {
                            "json": "Return ONLY one complete valid JSON object. No code fences, prose, comments or trailing text.",
                            "markdown": "Return ONLY the complete raw Markdown document, starting with its # heading. No outer code fence.",
                            "optional_markdown": "Return ONLY NONE or the complete raw Markdown document. No outer code fence.",
                            "text": "Return only the requested final text with no preamble.",
                        }.get(format_name, "Respect the declared output contract exactly.")
                        retry_prompt = (
                            model_request.messages[0].content
                            + "\n\n# RETRY AFTER RECOVERABLE OUTPUT FAILURE\n"
                            + f"The previous attempt failed the execution output contract ({last_retry_code or 'unknown'}). "
                              f"Regenerate from scratch in at most {max(200, int(attempt_max * 0.32))} words/tokens-equivalent. "
                              + contract_hint + " Preserve all mandatory information. "
                              "Use compact structures where appropriate and stop immediately after the required output is complete."
                        )
                        attempt_request = model_request.model_copy(update={
                            "messages": [ModelMessage(role=ModelRole.USER, content=retry_prompt)],
                            "max_output_tokens": attempt_max,
                        })
                    try:
                        with timed_span("langgraph.model", model=attempt_request.model or "default", attempt=attempt + 1):
                            candidate = await self._model_provider.generate(attempt_request)
                        # Output-contract validation belongs to the common execution runtime.
                        # A syntactically incomplete JSON/Markdown response is recoverable in
                        # exactly the same way as provider-level max_tokens truncation.
                        normalized = normalize_output(request, candidate.content)
                        model_result = candidate.model_copy(update={"content": normalized})
                        await self._executions.add_event(execution.id, "execution.model.attempt.completed", {
                            "attempt": attempt + 1,
                            "max_output_tokens": attempt_max,
                            "output_format": request.constraints.get("output_format", "text"),
                        })
                        break
                    except ModelProviderError as exc:
                        recoverable = exc.code in {"ANTHROPIC_OUTPUT_TRUNCATED", "INVALID_AGENT_OUTPUT"}
                        last_retry_code = exc.code
                        await self._executions.add_event(execution.id, "execution.model.attempt.failed", {
                            "attempt": attempt + 1,
                            "max_output_tokens": attempt_max,
                            "code": exc.code,
                            "recoverable_output_failure": recoverable,
                        })
                        if not recoverable or attempt == max_attempts - 1:
                            raise
                if model_result is None:
                    raise RuntimeError("Model execution produced no result")
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
        GraphRegistry.attach(
            GraphRegistry.graph_key(skill_definition),
            builder,
            self,
            execution,
        )
        return builder


__all__ = ["LangGraphAgentRuntime", "LangGraphState"]
