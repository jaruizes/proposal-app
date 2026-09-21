"""Section-level proposal workflow inside the Agent Platform LangGraph runtime.

The application owns the section contract. The graph owns execution and review;
no proposal text is persisted as canonical until the complete graph succeeds.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from langgraph.graph import END, StateGraph

from agent_platform.application.cache import stable_cache_key
from agent_platform.application.models import ModelMessage, ModelProviderError, ModelRequest, ModelResult, ModelRole, ModelUsage
from agent_platform.application.observability import PROPOSAL_STEP_COST, PROPOSAL_STEP_TOKENS, timed_span
from agent_platform.application.proposal_retrieval import ProposalReferenceRetriever
from agent_platform.config import get_settings
from agent_platform.domain import AgentExecutionRequest, CognitiveContext


class ProposalPlanError(ValueError):
    pass


class ProposalBudgetExceeded(ProposalPlanError):
    pass


_SECTION_BUDGETS = {
    "SUMMARY": {"words": 450, "tokens": 1400},
    "STANDARD": {"words": 800, "tokens": 2400},
    "DETAILED": {"words": 1200, "tokens": 3600},
}


def _section_budget(depth: str) -> dict[str, int]:
    return _SECTION_BUDGETS.get(depth, _SECTION_BUDGETS["STANDARD"])


def _approved_artifacts(request: AgentExecutionRequest) -> dict[str, str]:
    """Parse canonical approved artifacts from the backend context deterministically."""
    context = request.context.get("business_context", "")
    marker = "# APPROVED OFFER ARTIFACTS\n"
    guidance_marker = "\n\n# PROPOSAL GUIDANCE JSON\n"
    if not isinstance(context, str) or marker not in context:
        return {}
    raw = context.split(marker, 1)[1]
    if guidance_marker in raw:
        raw = raw.split(guidance_marker, 1)[0]

    names = {
        "OPPORTUNITY_BRIEF": "opportunityBrief",
        "QUESTIONS": "questions",
        "TECHNOLOGY": "technology",
        "SOLUTION": "solution",
        "DELIVERY_PLAN": "deliveryPlan",
    }
    matches = list(re.finditer(
        r"(?m)^# (OPPORTUNITY_BRIEF|QUESTIONS|TECHNOLOGY|SOLUTION|DELIVERY_PLAN)\s*$",
        raw,
    ))
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        content_start = match.end()
        content_end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        value = raw[content_start:content_end].strip()
        if value:
            result[names[match.group(1)]] = value
    return result


def _section_context(pack: dict[str, Any], section: dict[str, str]) -> dict[str, Any]:
    """Select canonical artifacts relevant to one proposal section without another LLM call."""
    text = (section.get("name", "") + " " + section.get("guidance", "")).casefold()
    keys = {"opportunityBrief"}

    rules = [
        (("resumen", "summary", "executive", "valor", "value"), {"solution", "deliveryPlan"}),
        (("reto", "context", "understand", "necesidad"), {"questions"}),
        (("objetiv", "alcance", "scope", "goal"), {"questions"}),
        (("requis", "condicion", "constraint"), {"questions", "technology"}),
        (("estrateg", "strategy"), {"solution", "deliveryPlan"}),
        (("solución", "solution", "technical"), {"solution", "technology"}),
        (("arquitect", "integr", "datos", "data"), {"solution", "technology"}),
        (("ejecución", "delivery", "workstream", "metodolog"), {"deliveryPlan", "solution"}),
        (("calidad", "risk", "riesg", "supuest", "assumption"), {"solution", "deliveryPlan", "questions"}),
        (("diferenci", "próxim", "next step", "valor añadido"), {"solution", "deliveryPlan"}),
    ]
    for needles, additions in rules:
        if any(needle in text for needle in needles):
            keys.update(additions)

    if len(keys) == 1:
        keys.update({"solution", "deliveryPlan"})
    return {key: pack[key] for key in keys if key in pack}



def _proposal_mode(request: AgentExecutionRequest) -> str:
    context = request.context.get("business_context", "")
    requested = "SPLIT"
    if isinstance(context, str):
        match = re.search(r"^# PROPOSAL MODE\s*\n(SINGLE|SPLIT)\s*$", context, re.MULTILINE)
        if match:
            requested = match.group(1)

    if requested == "SINGLE":
        sections = configured_sections(request)
        estimated_words = sum(_section_budget(section["depth"])["words"] for section in sections)
        # A long requested document is not a safe single-pass generation even if its
        # input context is small. Route before spending a doomed 12k-token call.
        if len(sections) > 6 or estimated_words > 8_000:
            return "SPLIT"
    return requested



def configured_sections(request: AgentExecutionRequest) -> list[dict[str, str]]:
    context = request.context.get("business_context", "")
    marker = "# PROPOSAL GUIDANCE JSON\n"
    if not isinstance(context, str) or marker not in context:
        raise ProposalPlanError("Structured proposal guidance is required")
    raw = context.split(marker, 1)[1].strip()
    try:
        guidance, _ = json.JSONDecoder().raw_decode(raw)
    except (ValueError, TypeError) as exc:
        raise ProposalPlanError("Invalid proposal guidance JSON") from exc
    if not isinstance(guidance, dict) or not isinstance(guidance.get("sections"), list):
        raise ProposalPlanError("Proposal guidance must contain sections")
    sections: list[dict[str, str]] = []
    names: set[str] = set()
    for item in guidance["sections"]:
        if not isinstance(item, dict):
            raise ProposalPlanError("Invalid proposal section")
        if not isinstance(item.get("enabled", True), bool):
            raise ProposalPlanError("Section enabled must be a boolean")
        if item.get("enabled", True) is False:
            continue
        name = item.get("name")
        depth = item.get("depth", "STANDARD")
        instructions = item.get("guidance", "")
        if not isinstance(name, str) or not name.strip() or "\n" in name or name.strip().casefold() in names:
            raise ProposalPlanError("Proposal section names must be unique, nonempty single lines")
        if depth not in {"SUMMARY", "STANDARD", "DETAILED"} or not isinstance(instructions, str):
            raise ProposalPlanError(f"Invalid guidance for section {name}")
        names.add(name.strip().casefold())
        sections.append({"name": name.strip(), "depth": depth, "guidance": instructions})
    if not sections:
        raise ProposalPlanError("At least one proposal section must be enabled")
    return sections


def _json_object(content: str, label: str) -> dict[str, Any]:
    raw = content.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw).strip()
    try:
        result = json.loads(raw)
    except ValueError as exc:
        raise ProposalPlanError(f"{label} returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise ProposalPlanError(f"{label} must return a JSON object")
    return result


def _json_response(content: str) -> dict[str, Any]:
    result = _json_object(content, "Global review")
    if not isinstance(result.get("issues"), list):
        raise ProposalPlanError("Global review must contain an issues array")
    return result


def _section_body(raw: str, name: str) -> str:
    """Normalize harmless Markdown deviations while preserving section content.

    The proposal assembler owns H1/H2. Models occasionally repeat the configured
    section title or introduce H1/H2 subheadings despite the output contract.
    Treat those as formatting deviations: remove a repeated section heading and
    demote remaining H1/H2 headings to H3 rather than failing the whole proposal.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:markdown|md)?\s*|\s*```$", "", text).strip()

    escaped = re.escape(name.strip())
    repeated_heading = re.compile(
        rf"^\s*#{{1,2}}\s+(?:\*\*)?{escaped}(?:\*\*)?\s*[:\-–—]?\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    text = repeated_heading.sub("", text, count=1).strip()

    # Section bodies may use subsections, but the canonical proposal reserves
    # levels 1 and 2 for the document and configured section headings.
    text = re.sub(r"^\s*#{1,2}\s+(.+?)\s*$", r"### \1", text, flags=re.MULTILINE).strip()

    if not text:
        raise ProposalPlanError(f"Invalid content for section {name}")
    return text


def _assemble(title: str, sections: list[dict[str, str]], drafts: dict[str, str]) -> str:
    if set(drafts) != {section["name"] for section in sections}:
        raise ProposalPlanError("Proposal is missing one or more sections")
    return "# " + title + "\n\n" + "\n\n".join(
        f"## {section['name']}\n\n{_section_body(drafts[section['name']], section['name'])}"
        for section in sections
    ) + "\n"


def add_proposal_nodes(builder: StateGraph, runtime, execution) -> None:
    """Attach the proposal stages after build_context, ending with model_result."""
    semaphore = asyncio.Semaphore(3)
    db_lock = asyncio.Lock()
    budget_lock = asyncio.Lock()
    calls: list[ModelResult] = []
    step_usage: list[dict[str, Any]] = []
    settings = get_settings()
    checkpoint_ttl = settings.proposal_checkpoint_ttl_seconds
    consumed = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "cost_usd": 0.0}

    def estimated_cost(usage: ModelUsage) -> float:
        million = 1_000_000.0
        return (
            usage.input_tokens * settings.anthropic_input_cost_per_million_usd
            + usage.output_tokens * settings.anthropic_output_cost_per_million_usd
            + usage.cache_read_tokens * settings.anthropic_cache_read_cost_per_million_usd
            + usage.cache_write_tokens * settings.anthropic_cache_write_cost_per_million_usd
        ) / million

    def output_budget_exhausted(reserve_tokens: int = 0) -> bool:
        return consumed["output"] + reserve_tokens >= settings.proposal_output_token_budget

    async def assert_budget(stage: str, estimated_input_tokens: int = 0) -> None:
        """Hard guardrails only; output-token budget is a soft degradation threshold."""
        async with budget_lock:
            if consumed["input"] + estimated_input_tokens > settings.proposal_input_token_budget:
                raise ProposalBudgetExceeded(
                    f"Proposal input token budget would be exceeded before {stage}: "
                    f"{consumed['input']} used, {settings.proposal_input_token_budget} allowed"
                )
            if consumed["cost_usd"] >= settings.proposal_cost_budget_usd:
                raise ProposalBudgetExceeded(
                    f"Proposal cost budget exceeded before {stage}: "
                    f"${consumed['cost_usd']:.4f} used, ${settings.proposal_cost_budget_usd:.2f} allowed"
                )

    async def note_soft_budget(stage: str, *, reserve_tokens: int = 0) -> bool:
        exhausted = output_budget_exhausted(reserve_tokens)
        if exhausted:
            await add_event("proposal.budget.soft_limit", {
                "stage": stage,
                "output_tokens": consumed["output"],
                "soft_limit": settings.proposal_output_token_budget,
                "reserve_tokens": reserve_tokens,
                "action": "skip_optional_work",
            })
        return exhausted
    async def record_step(stage: str, payload: dict, result: ModelResult, *, reused: bool = False) -> None:
        usage = result.usage
        cost = 0.0 if reused else estimated_cost(usage)
        async with budget_lock:
            if not reused:
                consumed["input"] += usage.input_tokens
                consumed["output"] += usage.output_tokens
                consumed["cache_read"] += usage.cache_read_tokens
                consumed["cache_write"] += usage.cache_write_tokens
                consumed["cost_usd"] += cost
            item = {
                "stage": stage,
                "section": payload.get("section"),
                "reused": reused,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "cache_read_tokens": usage.cache_read_tokens,
                "cache_write_tokens": usage.cache_write_tokens,
                "estimated_cost_usd": round(cost, 6),
                "cumulative_cost_usd": round(consumed["cost_usd"], 6),
            }
            step_usage.append(item)
        await add_event("proposal.step.usage", item)
        if not reused:
            for token_type, value in (
                ("input", usage.input_tokens),
                ("output", usage.output_tokens),
                ("cache_read", usage.cache_read_tokens),
                ("cache_write", usage.cache_write_tokens),
            ):
                if value:
                    PROPOSAL_STEP_TOKENS.labels(stage, token_type).inc(value)
            if cost:
                PROPOSAL_STEP_COST.labels(stage).inc(cost)
        if not reused:
            await assert_budget(stage)

    async def add_event(event_type: str, payload: dict) -> None:
        # All proposal substeps share the request-scoped SQLAlchemy AsyncSession.
        # AsyncSession/asyncpg cannot execute concurrent DB operations on one connection,
        # so serialize event persistence while keeping model calls concurrent.
        async with db_lock:
            await runtime._executions.add_event(execution.id, event_type, payload)

    async def generate(
        base: ModelRequest,
        instruction: str,
        event: str,
        payload: dict,
        *,
        max_output_tokens: int | None = None,
        retry_on_truncation: bool = True,
    ) -> ModelResult:
        prompt = base.messages[0].content + "\n\n# Current stage\n" + instruction
        effective_max = max_output_tokens or base.max_output_tokens
        checkpoint_key = stable_cache_key({
            "version": 2,
            "stage": event,
            "payload": payload,
            "model": base.model,
            "system_prompt": base.system_prompt,
            "base_prompt": base.messages[0].content,
            "cacheable_context": base.cacheable_context,
            "instruction": instruction,
            "max_output_tokens": effective_max,
        })

        # Cross-execution durable checkpoint. In production the shared cache is Valkey,
        # so a retry with the same exact inputs can reuse completed proposal substeps
        # even though the outer AgentExecution/LangGraph thread id changed.
        if runtime._cache is not None:
            cached = await runtime._cache.get_json("proposal-step", checkpoint_key)
            if cached is not None:
                result = ModelResult.model_validate(cached).model_copy(update={
                    "usage": ModelUsage(),
                    "provider_request_id": None,
                    "metadata": {
                        **ModelResult.model_validate(cached).metadata,
                        "proposal_checkpoint_hit": True,
                    },
                })
                await add_event("proposal.step.reused", {
                    **payload,
                    "stage": event,
                    "checkpoint_key": checkpoint_key,
                })
                await record_step(event, payload, result, reused=True)
                return result

        model_request = base.model_copy(update={
            "system_prompt": (base.system_prompt or "") +
                "\n\n# Execution mode\nThis is an intermediate proposal workflow stage. "
                "Follow the current stage output format. The graph assembles the canonical document. "
                "Respect the requested size budget; never expand beyond it.",
            "messages": [ModelMessage(role=ModelRole.USER, content=prompt)],
            "max_output_tokens": effective_max,
            "cache_system_prompt": True,
            "cacheable_context": base.cacheable_context,
        })
        estimated_input = max(1, (
            len(model_request.system_prompt or "")
            + len(model_request.cacheable_context or "")
            + len(prompt)
        ) // 4)
        await assert_budget(event, estimated_input)
        max_attempts = 3 if retry_on_truncation else 1
        async with semaphore:
            for attempt in range(max_attempts):
                if attempt == 0:
                    attempt_max = effective_max
                    attempt_prompt = prompt
                else:
                    factor = 0.65 if attempt == 1 else 0.40
                    attempt_max = min(effective_max, max(600, int(effective_max * factor)))
                    target_words = max(250, int(attempt_max * 0.32))
                    attempt_prompt = (
                        prompt
                        + "\n\n# HARD RETRY SIZE LIMIT\n"
                        + f"The previous response hit max_tokens. Regenerate from scratch in no more than {target_words} words "
                        "while preserving every material fact required by this stage. "
                        "Use compact tables/bullets where appropriate. Do not add commentary, preambles or repeated context. "
                        "For JSON stages, return only the required JSON and keep values terse."
                    )

                request_for_attempt = model_request.model_copy(update={
                    "messages": [ModelMessage(role=ModelRole.USER, content=attempt_prompt)],
                    "max_output_tokens": attempt_max,
                })
                try:
                    with timed_span("langgraph.proposal.model", stage=event, model=base.model or "default"):
                        result = await runtime._model_provider.generate(request_for_attempt)
                    calls.append(result)
                    if runtime._cache is not None:
                        await runtime._cache.set_json(
                            "proposal-step",
                            checkpoint_key,
                            result.model_dump(mode="json"),
                            ttl_seconds=checkpoint_ttl,
                        )
                    await record_step(event, {**payload, "attempt": attempt + 1}, result)
                    await add_event(event, {
                        **payload,
                        "attempt": attempt + 1,
                        "model": result.model,
                        "max_output_tokens": request_for_attempt.max_output_tokens,
                        "checkpoint_key": checkpoint_key,
                    })
                    return result
                except Exception as exc:
                    truncated = getattr(exc, "code", None) == "ANTHROPIC_OUTPUT_TRUNCATED"

                    # Truncated provider calls still cost money. Record their real usage
                    # so budgets/telemetry do not under-report failed generations.
                    if truncated and getattr(exc, "usage", None) is not None:
                        partial = ModelResult(
                            content=getattr(exc, "partial_content", "") or "",
                            model=getattr(exc, "model", None) or base.model or "unknown",
                            usage=exc.usage,
                            provider_request_id=getattr(exc, "provider_request_id", None),
                            finish_reason="max_tokens",
                            metadata={"truncated": True, "stage": event},
                        )
                        calls.append(partial)
                        await record_step(
                            event,
                            {**payload, "attempt": attempt + 1, "truncated": True},
                            partial,
                        )

                    if truncated and not retry_on_truncation:
                        raise
                    if not truncated and not getattr(exc, "retryable", False):
                        raise
                    if attempt == max_attempts - 1:
                        section = payload.get("section")
                        location = f" for section {section!r}" if section else ""
                        raise ModelProviderError(
                            "PROPOSAL_STEP_TRUNCATED",
                            f"Proposal substep {event}{location} repeatedly reached max_tokens after {max_attempts} attempts",
                        ) from exc

                    next_factor = 0.65 if attempt == 0 else 0.40
                    await add_event("proposal.model.retry", {
                        **payload,
                        "stage": event,
                        "attempt": attempt + 1,
                        "reason": "output_truncated" if truncated else "retryable_provider_error",
                        "next_max_output_tokens": min(effective_max, max(600, int(effective_max * next_factor))),
                    })
        raise AssertionError("Unreachable")

    async def base_request(state: dict, section: dict[str, str] | None = None) -> ModelRequest:
        request = AgentExecutionRequest.model_validate(state["request"])
        context = CognitiveContext.model_validate(state["cognitive_context"])
        agent = await runtime._agents.get(request.agent_key)
        skill = await runtime._skills.get(request.skill_key)
        assembled = runtime._prompt_assembler.build(agent, skill, request, context)

        business_context = request.context.get("business_context", "")
        state_pack = state.get("proposal_context_pack")
        pack = state_pack if isinstance(state_pack, dict) else _approved_artifacts(request)

        if isinstance(business_context, str):
            if isinstance(state_pack, dict):
                # Once the large-context pack exists, do not keep injecting the original
                # approved artifacts into every section call.
                offer_header = business_context.split("# APPROVED OFFER ARTIFACTS\n", 1)[0].strip()
            else:
                pack_marker = "# PROPOSAL CONTEXT PACK (authoritative compact representation)\n"
                offer_header = business_context.split(pack_marker, 1)[0].strip()
        else:
            offer_header = ""

        selected = _section_context(pack, section) if section is not None else {}
        cacheable_parts = ["# Current offer", offer_header]
        if selected:
            cacheable_parts.extend([
                "# Section-specific proposal context",
                json.dumps(selected, ensure_ascii=False, separators=(",", ":"), default=str),
            ])
        return assembled.model_copy(update={
            "messages": [ModelMessage(role=ModelRole.USER, content=f"# Task\n{request.objective}")],
            "cache_system_prompt": True,
            "cacheable_context": "\n\n".join(part for part in cacheable_parts if part),
        })

    async def validated_section_body(
        base: ModelRequest,
        raw: str,
        name: str,
        *,
        source_stage: str,
    ) -> str:
        try:
            return _section_body(raw, name)
        except ProposalPlanError:
            await add_event("proposal.section.format.invalid", {
                "section": name,
                "source_stage": source_stage,
            })
            repaired = await generate(
                base,
                (
                    f"Repair ONLY the Markdown formatting of section {name!r}. "
                    "Preserve all factual content, wording, tables, lists, citations and meaning. "
                    "Return the section BODY only: no section title, no level-one heading and no level-two heading. "
                    "Level-three or deeper subheadings are allowed. Do not add, remove or reinterpret facts.\n\n"
                    "# Content to reformat\n"
                    + raw
                ),
                "proposal.section.format.repaired",
                {"section": name, "source_stage": source_stage},
                max_output_tokens=_SECTION_BUDGETS["DETAILED"]["tokens"],
            )
            return _section_body(repaired.content, name)

    async def compact_context(state: dict) -> dict:
        request = AgentExecutionRequest.model_validate(state["request"])
        pack = _approved_artifacts(request)
        required = {"opportunityBrief", "solution", "deliveryPlan"}
        missing = sorted(required - set(pack))
        if missing:
            raise ProposalPlanError(
                "Approved proposal artifacts are incomplete: " + ", ".join(missing)
            )
        await add_event("proposal.context.selected", {
            "mode": "split",
            "artifacts": sorted(pack),
            "llm_calls": 0,
        })
        return {"proposal_context_pack": pack}

    async def direct_proposal(state: dict) -> dict:
        request = AgentExecutionRequest.model_validate(state["request"])
        base = await base_request(state)
        business_context = request.context.get("business_context", "")
        guidance = configured_sections(request)

        references = []
        if runtime._proposal_retrieval_service is not None:
            retriever = ProposalReferenceRetriever(runtime._proposal_retrieval_service)
            async with db_lock:
                _, references, _ = await retriever.retrieve(
                    section_name="Documento de oferta",
                    guidance=" ".join(section.get("guidance", "") for section in guidance),
                    objective=request.objective,
                    top_k=3,
                )

        reference_text = ""
        if references:
            reference_text = (
                "\n\n# NON-FACTUAL REFERENCE PATTERNS\n"
                "Use these excerpts only for structure, tone and depth. Never copy customer facts or commitments.\n"
                + "\n\n".join(f"## {r.title}\n{r.content}" for r in references)
            )

        instruction = (
            "Write the complete canonical proposal.md in one coherent narrative voice. "
            "Return raw Markdown only, with one H1 title and the configured H2 sections in the given order. "
            "Use the APPROVED OFFER ARTIFACTS in context as factual authority. "
            "Do not expose internal workflow terms. Do not invent prices, numeric effort/staffing/duration, "
            "contractual commitments or customer facts. Maintain strong transitions between sections so the "
            "document reads as one authored proposal, not concatenated fragments.\n\n"
            "# Required proposal sections\n"
            + "\n".join(
                f"- {section['name']} ({section['depth']}): {section['guidance']}"
                for section in guidance
            )
            + reference_text
        )
        try:
            result = await generate(
                base,
                instruction,
                "proposal.single_pass",
                {"mode": "single", "sections": len(guidance)},
                max_output_tokens=12000,
                retry_on_truncation=False,
            )
            content = result.content.strip()
            missing = [
                section["name"]
                for section in guidance
                if f"## {section['name']}" not in content
            ]
            if not content.startswith("# ") or missing:
                await add_event("proposal.single_pass.fallback", {
                    "reason": "incomplete_structure",
                    "missing_sections": missing,
                })
                return {"proposal_force_split": True}
            return {"model_result": result.model_dump(mode="json"), "proposal_force_split": False}
        except ModelProviderError as exc:
            if getattr(exc, "code", None) == "ANTHROPIC_OUTPUT_TRUNCATED":
                await add_event("proposal.single_pass.fallback", {"reason": "output_truncated"})
                return {"proposal_force_split": True}
            raise

    def after_direct(state: dict) -> str:
        return "split" if state.get("proposal_force_split") else "done"

    async def plan(state: dict) -> dict:
        request = AgentExecutionRequest.model_validate(state["request"])
        sections = configured_sections(request)
        await add_event("proposal.plan.completed", {"sections": [s["name"] for s in sections]})
        return {"proposal_sections": sections}

    async def retrieve_references(state: dict) -> dict:
        request = AgentExecutionRequest.model_validate(state["request"])
        sections = state["proposal_sections"]
        if runtime._proposal_retrieval_service is None:
            await add_event("proposal.retrieval.summary", {"enabled": False, "sections": len(sections), "hits": 0})
            return {"proposal_references": {section["name"]: [] for section in sections}}

        retriever = ProposalReferenceRetriever(runtime._proposal_retrieval_service)

        async def one(section: dict):
            # The retrieval service and ontology repository are backed by the same
            # request-scoped AsyncSession as execution persistence. Serialize the DB-bound
            # retrieval portion; model drafting/review below remains concurrent.
            async with db_lock:
                section_type, references, metadata = await retriever.retrieve(
                    section_name=section["name"],
                    guidance=section.get("guidance", ""),
                    objective=request.objective,
                    top_k=3,
                )
            safe_hits = [
                {
                    "title": ref.title,
                    "document_id": ref.document_id,
                    "chunk_id": ref.chunk_id,
                    "score": ref.score,
                    "source_uri": ref.source_uri,
                    "section_type": ref.section_type,
                }
                for ref in references
            ]
            await add_event("proposal.section.retrieval", {
                "section": section["name"],
                "section_type": section_type,
                "query": f"{section['name']}. {section.get('guidance','')}".strip(),
                "hits": safe_hits,
                "retrieval_metadata": {
                    "vector_candidates": metadata.get("vector_candidates"),
                    "keyword_candidates": metadata.get("keyword_candidates"),
                    "graph_candidates": metadata.get("graph_candidates"),
                    "relevance_filtering": metadata.get("relevance_filtering"),
                },
            })
            return section["name"], [
                {
                    "title": ref.title,
                    "document_id": ref.document_id,
                    "chunk_id": ref.chunk_id,
                    "score": ref.score,
                    "content": ref.content,
                    "source_uri": ref.source_uri,
                    "section_type": ref.section_type,
                }
                for ref in references
            ]

        results = {}
        for section in sections:
            name, references = await one(section)
            results[name] = references
        await add_event("proposal.retrieval.summary", {
            "enabled": True,
            "sections": len(sections),
            "hits": sum(len(items) for items in results.values()),
            "sections_with_hits": sum(1 for items in results.values() if items),
        })
        return {"proposal_references": results}

    def reference_prompt(references: list[dict]) -> str:
        if not references:
            return "\n\n# Reference patterns\nNo sufficiently relevant reference proposal was found. Continue using only current-offer evidence and human guidance."
        rendered = []
        for index, ref in enumerate(references, start=1):
            rendered.append(
                f"## Reference pattern {index}\n"
                f"Source: {ref['title']} ({ref['source_uri'] or ref['document_id']})\n"
                f"Retrieval score: {ref['score']:.4f}\n"
                f"{ref['content']}"
            )
        return (
            "\n\n# Reference patterns — NON-FACTUAL\n"
            "The following excerpts are historical reference material. Use them ONLY for structure, depth, terminology patterns and presentation style. "
            "NEVER transfer customer facts, technologies, commitments, prices, dates, staffing or claims into the current offer unless independently supported by approved current-offer evidence.\n\n"
            + "\n\n".join(rendered)
        )

    async def draft(state: dict) -> dict:
        sections = state["proposal_sections"]

        async def one(section: dict) -> tuple[str, str]:
            base = await base_request(state, section)
            name = section["name"]
            references = state.get("proposal_references", {}).get(name, [])
            budget = _section_budget(section["depth"])
            result = await generate(base, (
                f"Write ONLY the body of section {name!r} in Markdown, without its heading. "
                f"Depth: {section['depth']}. Human instructions: {section['guidance']}\n"
                f"Hard size budget: maximum {budget['words']} words. Prefer concise tables/lists over repetitive prose. "
                "Use approved current-offer evidence as the ONLY factual and decision authority. Label open gaps. "
                "Do not invent prices, effort, staffing, dates, commitments or customer facts. "
                "Reference proposal excerpts, when present, are NON-FACTUAL style/depth patterns only. "
                "Do not introduce level-one or level-two headings."
                + reference_prompt(references)
            ), "proposal.section.drafted", {
                "section": name,
                "reference_hits": len(references),
                "word_budget": budget["words"],
            }, max_output_tokens=budget["tokens"])
            return name, await validated_section_body(base, result.content, name, source_stage="draft")

        results = []
        for section in sections:
            results.append(await one(section))
        return {"proposal_drafts": dict(results)}

    def final_result(
        *,
        proposal: str,
        model: str,
        provider_request_id: str | None,
        sections: list[dict[str, str]],
        reference_map: dict[str, list[dict]],
        normalized: list[dict[str, str]] | None = None,
        quality_degraded: bool = False,
        skipped_quality_steps: list[str] | None = None,
    ) -> ModelResult:
        issues = normalized or []
        usage = ModelUsage(
            input_tokens=sum(call.usage.input_tokens for call in calls),
            output_tokens=sum(call.usage.output_tokens for call in calls),
            cache_read_tokens=sum(call.usage.cache_read_tokens for call in calls),
            cache_write_tokens=sum(call.usage.cache_write_tokens for call in calls),
        )
        return ModelResult(
            content=proposal,
            model=model,
            usage=usage,
            provider_request_id=provider_request_id,
            metadata={
                "proposal_sections": len(sections),
                "model_calls": len(calls),
                "reference_hits": sum(len(items) for items in reference_map.values()),
                "reference_sections": {name: len(items) for name, items in reference_map.items()},
                "global_review_issues": len(issues),
                "global_review_blocking_issues": sum(
                    1 for item in issues if item.get("severity") == "BLOCKING"
                ),
                "global_review_corrected": bool(issues) and not quality_degraded,
                "quality_degraded": quality_degraded,
                "skipped_quality_steps": skipped_quality_steps or [],
                "proposal_step_usage": step_usage,
                "proposal_budget": {
                    "input_tokens": settings.proposal_input_token_budget,
                    "output_tokens": settings.proposal_output_token_budget,
                    "cost_usd": settings.proposal_cost_budget_usd,
                },
                "proposal_consumed": {
                    "input_tokens": consumed["input"],
                    "output_tokens": consumed["output"],
                    "cache_read_tokens": consumed["cache_read"],
                    "cache_write_tokens": consumed["cache_write"],
                    "estimated_cost_usd": round(consumed["cost_usd"], 6),
                },
            },
        )

    async def review_sections(state: dict) -> dict:
        sections = state["proposal_sections"]
        drafts = dict(state["proposal_drafts"])
        skipped: list[str] = []

        # Reviews are quality enhancement, not required to produce a usable proposal.
        # Keep enough output headroom for one global review/finalization. If the drafts
        # already consumed most of the soft budget, preserve them instead of failing.
        if await note_soft_budget("proposal.section.reviewed", reserve_tokens=6000):
            skipped.append("section_reviews")
            await add_event("proposal.quality.degraded", {
                "reason": "output_budget",
                "skipped": skipped,
                "output_tokens": consumed["output"],
            })
            return {
                "proposal_drafts": drafts,
                "proposal_quality_degraded": True,
                "proposal_skipped_quality_steps": skipped,
            }

        for section in sections:
            # Re-check before every review because a previous review/correction may have
            # consumed the remaining soft budget.
            if await note_soft_budget("proposal.section.reviewed", reserve_tokens=4500):
                skipped.append(f"review:{section['name']}")
                continue

            base = await base_request(state, section)
            name = section["name"]
            current = drafts[name]
            budget = _section_budget(section["depth"])

            review_result = await generate(base, (
                f"Review ONLY section {name!r}. Do not rewrite it. "
                f"Required depth: {section['depth']}. Human instructions: {section['guidance']}\n"
                "Check only material factual support, missing required coverage, inconsistent terminology, "
                "unsupported commitments and explicit gaps. Ignore stylistic preferences and minor repetition. "
                "Return ONLY JSON: {\"issues\":[\"specific correction\"]}. "
                "Return {\"issues\":[]} when the section is acceptable. Maximum four issues.\n\n"
                f"# Candidate section\n{current}"
            ), "proposal.section.reviewed", {
                "section": name,
                "review_mode": "issues-only",
            }, max_output_tokens=700)

            issues = _json_response(review_result.content)["issues"]
            clean_issues = [
                str(item).strip()
                for item in issues
                if isinstance(item, str) and str(item).strip()
            ]
            if not clean_issues:
                await add_event("proposal.section.accepted", {
                    "section": name,
                    "reused_draft": True,
                })
                continue

            # Correction is optional once the soft budget is close. The human approval
            # gate is the final authority, so keep the evidence-backed draft rather than
            # failing the entire business phase.
            if await note_soft_budget("proposal.section.corrected", reserve_tokens=3500):
                skipped.append(f"correction:{name}")
                await add_event("proposal.section.correction.skipped", {
                    "section": name,
                    "issues": clean_issues,
                    "reason": "output_budget",
                })
                continue

            correction = await generate(base, (
                f"Revise ONLY the body of section {name!r}. Return its complete revised body, with no heading. "
                f"Keep it within {budget['words']} words. "
                "Preserve supported content and make only changes required by these review findings:\n"
                + "\n".join(f"- {item}" for item in clean_issues)
                + "\n\n# Current body\n" + current
            ), "proposal.section.corrected", {
                "section": name,
                "issues": clean_issues,
                "word_budget": budget["words"],
            }, max_output_tokens=min(budget["tokens"], 3200))
            drafts[name] = await validated_section_body(
                base, correction.content, name, source_stage="section-review"
            )

        degraded = bool(skipped)
        if degraded:
            await add_event("proposal.quality.degraded", {
                "reason": "output_budget",
                "skipped": skipped,
                "output_tokens": consumed["output"],
            })
        return {
            "proposal_drafts": drafts,
            "proposal_quality_degraded": degraded,
            "proposal_skipped_quality_steps": skipped,
        }

    async def assemble(state: dict) -> dict:
        request = AgentExecutionRequest.model_validate(state["request"])
        business_context = request.context.get("business_context", "")
        match = re.search(r"^Offer name: (.+)$", business_context, re.M) if isinstance(business_context, str) else None
        title = request.context.get("proposal_title") or (match.group(1) if match else "Oferta detallada")
        if not isinstance(title, str) or not title.strip() or "\n" in title:
            title = "Oferta detallada"
        content = _assemble(title.strip(), state["proposal_sections"], state["proposal_drafts"])
        await add_event("proposal.assembled", {"sections": len(state["proposal_sections"])})
        return {"proposal_content": content}

    def final_model_result(
        state: dict,
        proposal: str,
        *,
        model: str | None = None,
        provider_request_id: str | None = None,
        normalized_issues: list[dict[str, str]] | None = None,
        global_review_skipped: bool = False,
        skip_reason: str | None = None,
        corrected_sections: list[str] | None = None,
        skipped_corrections: list[str] | None = None,
    ) -> ModelResult:
        issues = normalized_issues or []
        usage = ModelUsage(
            input_tokens=sum(call.usage.input_tokens for call in calls),
            output_tokens=sum(call.usage.output_tokens for call in calls),
            cache_read_tokens=sum(call.usage.cache_read_tokens for call in calls),
            cache_write_tokens=sum(call.usage.cache_write_tokens for call in calls),
        )
        reference_map = state.get("proposal_references", {})
        return ModelResult(
            content=proposal,
            model=model or (calls[-1].model if calls else "unknown"),
            usage=usage,
            provider_request_id=provider_request_id or (calls[-1].provider_request_id if calls else None),
            metadata={
                "proposal_sections": len(state.get("proposal_sections", [])),
                "model_calls": len(calls),
                "reference_hits": sum(len(items) for items in reference_map.values()),
                "reference_sections": {name: len(items) for name, items in reference_map.items()},
                "global_review_issues": len(issues),
                "global_review_blocking_issues": sum(1 for item in issues if item.get("severity") == "BLOCKING"),
                "global_review_advisory_improvements": sum(1 for item in issues if item.get("severity") == "IMPROVEMENT"),
                "global_review_skipped": global_review_skipped,
                "global_review_skip_reason": skip_reason,
                "global_review_corrected": bool(corrected_sections),
                "global_review_corrected_sections": corrected_sections or [],
                "global_review_skipped_corrections": skipped_corrections or [],
                "proposal_step_usage": step_usage,
                "proposal_budget": {
                    "input_tokens": settings.proposal_input_token_budget,
                    "output_tokens": settings.proposal_output_token_budget,
                    "cost_usd": settings.proposal_cost_budget_usd,
                    "output_budget_mode": "soft",
                },
                "proposal_consumed": {
                    "input_tokens": consumed["input"],
                    "output_tokens": consumed["output"],
                    "cache_read_tokens": consumed["cache_read"],
                    "cache_write_tokens": consumed["cache_write"],
                    "estimated_cost_usd": round(consumed["cost_usd"], 6),
                },
            },
        )
    async def global_review(state: dict) -> dict:
        base = await base_request(state)
        sections = state["proposal_sections"]
        drafts = dict(state["proposal_drafts"])
        title = state["proposal_content"].splitlines()[0][2:]
        proposal = _assemble(title, sections, drafts)
        reference_map = state.get("proposal_references", {})
        skipped = list(state.get("proposal_skipped_quality_steps", []))
        already_degraded = bool(state.get("proposal_quality_degraded"))

        # The proposal is already complete and structurally valid here. Global review is
        # therefore optional. Never throw away the document because there is no remaining
        # soft output budget for another quality pass.
        if await note_soft_budget("proposal.global.reviewed", reserve_tokens=2500):
            skipped.append("global_review")
            await add_event("proposal.global.review.skipped", {
                "reason": "output_budget",
                "output_tokens": consumed["output"],
            })
            last = calls[-1] if calls else None
            final = final_result(
                proposal=proposal,
                model=last.model if last else (base.model or "unknown"),
                provider_request_id=last.provider_request_id if last else None,
                sections=sections,
                reference_map=reference_map,
                quality_degraded=True,
                skipped_quality_steps=skipped,
            )
            return {"model_result": final.model_dump(mode="json")}

        result = await generate(base, (
            "Review the complete proposal once for material cross-section quality issues. "
            "Focus only on factual contradictions, unsupported commitments, missing required coverage, "
            "or terminology inconsistencies that would materially mislead the customer. "
            "Do NOT report stylistic preferences, optional improvements or minor repetition. "
            "Do not rewrite the document. "
            "Return ONLY JSON: "
            "{\"issues\":[{\"section\":\"exact configured section name\","
            "\"severity\":\"BLOCKING|IMPROVEMENT\","
            "\"instruction\":\"specific correction\"}]}. "
            "Use BLOCKING only for issues that make the proposal materially incorrect or incomplete. "
            "Return an empty issues array when acceptable. Maximum five actionable issues.\n\n"
            f"# Candidate proposal\n{proposal}"
        ), "proposal.global.reviewed", {"pass": 1}, max_output_tokens=1200)

        issues = _json_response(result.content)["issues"]
        valid = {section["name"] for section in sections}
        normalized: list[dict[str, str]] = []
        for issue in issues:
            if (
                not isinstance(issue, dict)
                or issue.get("section") not in valid
                or not isinstance(issue.get("instruction"), str)
            ):
                continue
            severity = str(issue.get("severity") or "IMPROVEMENT").upper()
            if severity not in {"BLOCKING", "IMPROVEMENT"}:
                severity = "IMPROVEMENT"
            normalized.append({
                "section": issue["section"],
                "severity": severity,
                "instruction": issue["instruction"].strip(),
            })

        grouped: dict[str, list[str]] = {}
        for issue in normalized:
            if issue["instruction"]:
                grouped.setdefault(issue["section"], []).append(
                    f"[{issue['severity']}] {issue['instruction']}"
                )

        corrected_sections: list[str] = []
        for name, instructions in grouped.items():
            # Improvements are never worth failing the phase. Blocking findings may be
            # corrected while budget remains; otherwise surface them to the human reviewer.
            severities = {item["severity"] for item in normalized if item["section"] == name}
            if await note_soft_budget("proposal.section.revised", reserve_tokens=1800):
                skipped.append(f"global_correction:{name}")
                await add_event("proposal.global.correction.skipped", {
                    "section": name,
                    "severities": sorted(severities),
                    "reason": "output_budget",
                })
                continue

            section = next(item for item in sections if item["name"] == name)
            section_base = await base_request(state, section)
            budget = _section_budget(section["depth"])
            correction = await generate(section_base, (
                f"Revise ONLY the body of section {name!r}. No heading or other sections. "
                f"Keep the revised section within {min(budget['words'], 1000)} words. "
                "Preserve approved evidence and avoid unsupported commitments. "
                "Apply only the following material findings:\n"
                + "\n".join(f"- {item}" for item in instructions)
                + "\n\n# Current body\n" + drafts[name]
            ), "proposal.section.revised", {
                "section": name,
                "word_budget": min(budget["words"], 1000),
            }, max_output_tokens=min(budget["tokens"], 2600))

            drafts[name] = await validated_section_body(
                section_base, correction.content, name, source_stage="global-revision"
            )
            corrected_sections.append(name)

        if corrected_sections:
            proposal = _assemble(title, sections, drafts)
            await add_event("proposal.global.review.corrected", {
                "issues": len(normalized),
                "blocking": sum(1 for item in normalized if item["severity"] == "BLOCKING"),
                "improvements": sum(1 for item in normalized if item["severity"] == "IMPROVEMENT"),
                "sections_corrected": corrected_sections,
            })

        degraded = already_degraded or bool(skipped)
        if degraded:
            await add_event("proposal.quality.degraded", {
                "reason": "soft_budget_or_skipped_quality_work",
                "skipped": skipped,
                "unresolved_issues": [
                    item for item in normalized
                    if f"global_correction:{item['section']}" in skipped
                ],
            })

        final = final_result(
            proposal=proposal,
            model=result.model,
            provider_request_id=result.provider_request_id,
            sections=sections,
            reference_map=reference_map,
            normalized=normalized,
            quality_degraded=degraded,
            skipped_quality_steps=skipped,
        )
        return {"model_result": final.model_dump(mode="json")}

    builder.add_node("direct_proposal", direct_proposal)
    builder.add_node("compact_proposal_context", compact_context)
    builder.add_node("plan_proposal", plan)
    builder.add_node("retrieve_references", retrieve_references)
    builder.add_node("draft_sections", draft)
    builder.add_node("review_sections", review_sections)
    builder.add_node("assemble_proposal", assemble)
    builder.add_node("review_proposal", global_review)

    builder.add_conditional_edges(
        "build_context",
        lambda state: "single" if _proposal_mode(AgentExecutionRequest.model_validate(state["request"])) == "SINGLE" else "split",
        {"single": "direct_proposal", "split": "compact_proposal_context"},
    )
    builder.add_conditional_edges(
        "direct_proposal",
        after_direct,
        {"done": END, "split": "compact_proposal_context"},
    )
    builder.add_edge("compact_proposal_context", "plan_proposal")
    builder.add_edge("plan_proposal", "retrieve_references")
    builder.add_edge("retrieve_references", "draft_sections")
    builder.add_edge("draft_sections", "assemble_proposal")
    builder.add_edge("assemble_proposal", "review_proposal")
    builder.add_edge("review_proposal", END)
