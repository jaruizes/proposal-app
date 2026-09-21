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
from agent_platform.application.models import ModelMessage, ModelRequest, ModelResult, ModelRole, ModelUsage
from agent_platform.application.observability import timed_span
from agent_platform.application.proposal_retrieval import ProposalReferenceRetriever
from agent_platform.config import get_settings
from agent_platform.domain import AgentExecutionRequest, CognitiveContext


class ProposalPlanError(ValueError):
    pass


class ProposalBudgetExceeded(ProposalPlanError):
    pass


_SECTION_BUDGETS = {
    "SUMMARY": {"words": 700, "tokens": 2200},
    "STANDARD": {"words": 1200, "tokens": 3600},
    "DETAILED": {"words": 1800, "tokens": 5600},
}


def _section_budget(depth: str) -> dict[str, int]:
    return _SECTION_BUDGETS.get(depth, _SECTION_BUDGETS["STANDARD"])


def _proposal_context_pack(request: AgentExecutionRequest) -> dict[str, Any]:
    context = request.context.get("business_context", "")
    marker = "# PROPOSAL CONTEXT PACK (authoritative compact representation)\n"
    end_marker = "\n\n# PROPOSAL GUIDANCE JSON\n"
    if not isinstance(context, str) or marker not in context:
        return {}
    raw = context.split(marker, 1)[1]
    if end_marker in raw:
        raw = raw.split(end_marker, 1)[0]
    try:
        value = json.loads(raw.strip())
        return value if isinstance(value, dict) else {}
    except ValueError:
        return {}


def _section_context(pack: dict[str, Any], section: dict[str, str]) -> dict[str, Any]:
    """Select only context-pack slices relevant to one configured proposal section."""
    text = (section.get("name", "") + " " + section.get("guidance", "")).casefold()
    keys = {"customerAndOpportunity", "mandatoryRequirements", "evidenceIndex"}
    rules = [
        (("resumen", "summary", "executive", "valor", "value"), {"goalsAndScope", "strategy", "solutionHighlights", "differentiators", "risksAssumptionsAndTbds"}),
        (("reto", "context", "understand", "necesidad"), {"goalsAndScope", "strategy", "risksAssumptionsAndTbds"}),
        (("objetiv", "alcance", "scope", "goal"), {"goalsAndScope", "strategy", "risksAssumptionsAndTbds"}),
        (("requis", "condicion", "constraint"), {"goalsAndScope", "securityAndOperations", "risksAssumptionsAndTbds"}),
        (("estrateg", "strategy"), {"strategy", "goalsAndScope", "solutionHighlights", "differentiators"}),
        (("solución", "solution", "technical"), {"solutionHighlights", "architectureAndIntegrations", "securityAndOperations", "strategy"}),
        (("arquitect", "integr", "datos", "data"), {"architectureAndIntegrations", "solutionHighlights", "securityAndOperations"}),
        (("ejecución", "delivery", "workstream", "metodolog"), {"deliveryApproach", "risksAssumptionsAndTbds", "goalsAndScope"}),
        (("calidad", "risk", "riesg", "supuest", "assumption"), {"risksAssumptionsAndTbds", "securityAndOperations", "deliveryApproach"}),
        (("diferenci", "próxim", "next step", "valor añadido"), {"differentiators", "strategy", "solutionHighlights", "deliveryApproach"}),
    ]
    for needles, additions in rules:
        if any(needle in text for needle in needles):
            keys.update(additions)
    if len(keys) <= 3:
        keys.update({"goalsAndScope", "strategy", "solutionHighlights", "risksAssumptionsAndTbds"})
    return {key: pack[key] for key in keys if key in pack}


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


def _json_response(content: str) -> dict[str, Any]:
    raw = content.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw).strip()
    try:
        result = json.loads(raw)
    except ValueError as exc:
        raise ProposalPlanError("Global review returned invalid JSON") from exc
    if not isinstance(result, dict) or not isinstance(result.get("issues"), list):
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

    async def assert_budget(stage: str, estimated_input_tokens: int = 0) -> None:
        async with budget_lock:
            if consumed["input"] + estimated_input_tokens > settings.proposal_input_token_budget:
                raise ProposalBudgetExceeded(
                    f"Proposal input token budget would be exceeded before {stage}: "
                    f"{consumed['input']} used, {settings.proposal_input_token_budget} allowed"
                )
            if consumed["output"] >= settings.proposal_output_token_budget:
                raise ProposalBudgetExceeded(
                    f"Proposal output token budget exceeded before {stage}: "
                    f"{consumed['output']} used, {settings.proposal_output_token_budget} allowed"
                )
            if consumed["cost_usd"] >= settings.proposal_cost_budget_usd:
                raise ProposalBudgetExceeded(
                    f"Proposal cost budget exceeded before {stage}: "
                    f"${consumed['cost_usd']:.4f} used, ${settings.proposal_cost_budget_usd:.2f} allowed"
                )

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
                return result

        model_request = base.model_copy(update={
            "system_prompt": (base.system_prompt or "") +
                "\n\n# Execution mode\nThis is an intermediate proposal workflow stage. "
                "Follow the current stage output format. The graph assembles the canonical document. "
                "Respect the requested size budget; never expand beyond it.",
            "messages": [ModelMessage(role=ModelRole.USER, content=prompt)],
            "max_output_tokens": effective_max,
        })
        async with semaphore:
            for attempt in range(2):
                try:
                    request_for_attempt = model_request
                    if attempt:
                        request_for_attempt = model_request.model_copy(update={
                            "messages": [ModelMessage(
                                role=ModelRole.USER,
                                content=prompt +
                                    "\n\n# RETRY AFTER OUTPUT LIMIT\n"
                                    "Your previous response exceeded the output budget. "
                                    "Regenerate the requested output from scratch, materially more concise. "
                                    "Do not repeat context, do not add extra sections, and stop once the requested body/JSON is complete."
                            )]
                        })
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
                    if attempt or (not truncated and not getattr(exc, "retryable", False)):
                        raise
                    await add_event("proposal.model.retry", {
                        **payload,
                        "stage": event,
                        "reason": "output_truncated" if truncated else "retryable_provider_error",
                    })
        raise AssertionError("Unreachable")

    async def base_request(state: dict) -> ModelRequest:
        request = AgentExecutionRequest.model_validate(state["request"])
        context = CognitiveContext.model_validate(state["cognitive_context"])
        # Compose the same system prompt and bounded cognitive context used by other skills.
        agent = await runtime._agents.get(request.agent_key)
        skill = await runtime._skills.get(request.skill_key)
        return runtime._prompt_assembler.build(agent, skill, request, context)

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

        results = dict(await asyncio.gather(*(one(section) for section in sections)))
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
        base = await base_request(state)
        sections = state["proposal_sections"]

        async def one(section: dict) -> tuple[str, str]:
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

        results = await asyncio.gather(*(one(section) for section in sections))
        return {"proposal_drafts": dict(results)}

    async def review_sections(state: dict) -> dict:
        base = await base_request(state)

        async def one(section: dict) -> tuple[str, str]:
            name = section["name"]
            current = state["proposal_drafts"][name]
            budget = _section_budget(section["depth"])

            review = await generate(base, (
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
            }, max_output_tokens=1000)

            issues = _json_response(review.content)["issues"]
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
                return name, current

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
            }, max_output_tokens=budget["tokens"])
            return name, await validated_section_body(
                base, correction.content, name, source_stage="section-review"
            )

        results = await asyncio.gather(*(one(section) for section in state["proposal_sections"]))
        return {"proposal_drafts": dict(results)}

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

    async def global_review(state: dict) -> dict:
        base = await base_request(state)
        sections = state["proposal_sections"]
        drafts = dict(state["proposal_drafts"])
        title = state["proposal_content"].splitlines()[0][2:]
        proposal = _assemble(title, sections, drafts)

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
        ), "proposal.global.reviewed", {"pass": 1}, max_output_tokens=1800)

        issues = _json_response(result.content)["issues"]
        valid = {section["name"] for section in sections}
        normalized: list[dict[str, str]] = []
        for issue in issues:
            if (
                not isinstance(issue, dict)
                or issue.get("section") not in valid
                or not isinstance(issue.get("instruction"), str)
            ):
                raise ProposalPlanError("Global review referenced an invalid section")
            severity = str(issue.get("severity") or "IMPROVEMENT").upper()
            if severity not in {"BLOCKING", "IMPROVEMENT"}:
                severity = "IMPROVEMENT"
            normalized.append({
                "section": issue["section"],
                "severity": severity,
                "instruction": issue["instruction"].strip(),
            })

        if normalized:
            grouped: dict[str, list[str]] = {}
            for issue in normalized:
                if issue["instruction"]:
                    grouped.setdefault(issue["section"], []).append(
                        f"[{issue['severity']}] {issue['instruction']}"
                    )

            async def revise(name: str, instructions: list[str]) -> tuple[str, str]:
                section = next(item for item in sections if item["name"] == name)
                budget = _section_budget(section["depth"])
                correction = await generate(base, (
                    f"Revise ONLY the body of section {name!r}. No heading or other sections. "
                    f"Keep the revised section within {budget['words']} words. "
                    "Preserve approved evidence and avoid unsupported commitments. "
                    "Apply the following global review findings exactly; do not introduce unrelated changes:\n"
                    + "\n".join(f"- {item}" for item in instructions)
                    + "\n\n# Current body\n" + drafts[name]
                ), "proposal.section.revised", {
                    "section": name,
                    "word_budget": budget["words"],
                }, max_output_tokens=budget["tokens"])
                return name, await validated_section_body(
                    base, correction.content, name, source_stage="global-revision"
                )

            drafts.update(await asyncio.gather(
                *(revise(name, instructions) for name, instructions in grouped.items())
            ))
            proposal = _assemble(title, sections, drafts)
            await add_event("proposal.global.review.corrected", {
                "issues": len(normalized),
                "blocking": sum(1 for item in normalized if item["severity"] == "BLOCKING"),
                "improvements": sum(1 for item in normalized if item["severity"] == "IMPROVEMENT"),
                "sections_corrected": sorted(grouped),
            })

        usage = ModelUsage(
            input_tokens=sum(c.usage.input_tokens for c in calls),
            output_tokens=sum(c.usage.output_tokens for c in calls),
            cache_read_tokens=sum(c.usage.cache_read_tokens for c in calls),
            cache_write_tokens=sum(c.usage.cache_write_tokens for c in calls),
        )
        reference_map = state.get("proposal_references", {})
        final = ModelResult(
            content=proposal,
            model=result.model,
            usage=usage,
            provider_request_id=result.provider_request_id,
            metadata={
                "proposal_sections": len(sections),
                "model_calls": len(calls),
                "reference_hits": sum(len(items) for items in reference_map.values()),
                "reference_sections": {name: len(items) for name, items in reference_map.items()},
                "global_review_issues": len(normalized),
                "global_review_blocking_issues": sum(
                    1 for item in normalized if item["severity"] == "BLOCKING"
                ),
                "global_review_corrected": bool(normalized),
            },
        )
        return {"model_result": final.model_dump(mode="json")}

    builder.add_node("plan_proposal", plan)
    builder.add_node("retrieve_references", retrieve_references)
    builder.add_node("draft_sections", draft)
    builder.add_node("review_sections", review_sections)
    builder.add_node("assemble_proposal", assemble)
    builder.add_node("review_proposal", global_review)
    builder.add_edge("build_context", "plan_proposal")
    builder.add_edge("plan_proposal", "retrieve_references")
    builder.add_edge("retrieve_references", "draft_sections")
    builder.add_edge("draft_sections", "review_sections")
    builder.add_edge("review_sections", "assemble_proposal")
    builder.add_edge("assemble_proposal", "review_proposal")
    builder.add_edge("review_proposal", END)
