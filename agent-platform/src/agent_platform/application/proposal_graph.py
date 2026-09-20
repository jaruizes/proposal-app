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

from agent_platform.application.models import ModelMessage, ModelRequest, ModelResult, ModelRole, ModelUsage
from agent_platform.application.observability import timed_span
from agent_platform.domain import AgentExecutionRequest, CognitiveContext


class ProposalPlanError(ValueError):
    pass


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
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:markdown|md)?\s*|\s*```$", "", text).strip()
    heading = re.compile(r"^##\s+" + re.escape(name) + r"\s*$", re.M)
    text = heading.sub("", text, count=1).strip()
    if not text or re.search(r"^#{1,2}\s+", text, re.M):
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
    calls: list[ModelResult] = []

    async def generate(base: ModelRequest, instruction: str, event: str, payload: dict) -> ModelResult:
        prompt = base.messages[0].content + "\n\n# Current stage\n" + instruction
        model_request = base.model_copy(update={
            "system_prompt": (base.system_prompt or "") +
                "\n\n# Execution mode\nThis is an intermediate proposal workflow stage. "
                "Follow the current stage output format. The graph assembles the canonical document.",
            "messages": [ModelMessage(role=ModelRole.USER, content=prompt)],
        })
        async with semaphore:
            for attempt in range(2):
                try:
                    with timed_span("langgraph.proposal.model", stage=event, model=base.model or "default"):
                        result = await runtime._model_provider.generate(model_request)
                    calls.append(result)
                    await runtime._executions.add_event(execution.id, event, {**payload, "attempt": attempt + 1, "model": result.model})
                    return result
                except Exception as exc:
                    if attempt or not getattr(exc, "retryable", False):
                        raise
                    await runtime._executions.add_event(execution.id, "proposal.model.retry", {**payload, "stage": event})
        raise AssertionError("Unreachable")

    async def base_request(state: dict) -> ModelRequest:
        request = AgentExecutionRequest.model_validate(state["request"])
        context = CognitiveContext.model_validate(state["cognitive_context"])
        # Compose the same system prompt and bounded cognitive context used by other skills.
        agent = await runtime._agents.get(request.agent_key)
        skill = await runtime._skills.get(request.skill_key)
        return runtime._prompt_assembler.build(agent, skill, request, context)

    async def plan(state: dict) -> dict:
        request = AgentExecutionRequest.model_validate(state["request"])
        sections = configured_sections(request)
        await runtime._executions.add_event(execution.id, "proposal.plan.completed", {"sections": [s["name"] for s in sections]})
        return {"proposal_sections": sections}

    async def draft(state: dict) -> dict:
        base = await base_request(state)
        sections = state["proposal_sections"]

        async def one(section: dict) -> tuple[str, str]:
            name = section["name"]
            result = await generate(base, (
                f"Write ONLY the body of section {name!r} in Markdown, without its heading. "
                f"Depth: {section['depth']}. Human instructions: {section['guidance']}\n"
                "Use only approved current-offer evidence. Label open gaps. Do not invent prices, effort, staffing, "
                "dates, commitments or customer facts. Do not introduce level-one or level-two headings."
            ), "proposal.section.drafted", {"section": name})
            return name, _section_body(result.content, name)

        results = await asyncio.gather(*(one(section) for section in sections))
        return {"proposal_drafts": dict(results)}

    async def review_sections(state: dict) -> dict:
        base = await base_request(state)

        async def one(section: dict) -> tuple[str, str]:
            name = section["name"]
            current = state["proposal_drafts"][name]
            result = await generate(base, (
                f"Review and correct ONLY section {name!r}. Return its complete revised body, with no heading. "
                f"Required depth: {section['depth']}. Human instructions: {section['guidance']}\n"
                "Check factual support, omissions, terminology and prohibited invented commitments. "
                "Keep unsupported items explicit as gaps. No level-one or level-two headings.\n\n"
                f"# Candidate section\n{current}"
            ), "proposal.section.reviewed", {"section": name})
            return name, _section_body(result.content, name)

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
        await runtime._executions.add_event(execution.id, "proposal.assembled", {"sections": len(state["proposal_sections"])})
        return {"proposal_content": content}

    async def global_review(state: dict) -> dict:
        base = await base_request(state)
        sections = state["proposal_sections"]
        drafts = dict(state["proposal_drafts"])
        for pass_number in range(2):
            proposal = _assemble(state["proposal_content"].splitlines()[0][2:], sections, drafts)
            result = await generate(base, (
                "Review the complete proposal for cross-section contradictions, missing required coverage, "
                "unsupported claims, repetition and inconsistent terminology. Do not rewrite the document. "
                "Return ONLY JSON: {\"issues\":[{\"section\":\"exact configured section name\",\"instruction\":\"specific correction\"}]}. "
                "Return an empty issues array when acceptable. Maximum five actionable issues.\n\n"
                f"# Candidate proposal\n{proposal}"
            ), "proposal.global.reviewed", {"pass": pass_number + 1})
            issues = _json_response(result.content)["issues"]
            if not issues:
                usage = ModelUsage(
                    input_tokens=sum(c.usage.input_tokens for c in calls),
                    output_tokens=sum(c.usage.output_tokens for c in calls),
                    cache_read_tokens=sum(c.usage.cache_read_tokens for c in calls),
                    cache_write_tokens=sum(c.usage.cache_write_tokens for c in calls),
                )
                final = ModelResult(content=proposal, model=result.model, usage=usage,
                                    provider_request_id=result.provider_request_id,
                                    metadata={"proposal_sections": len(sections), "model_calls": len(calls)})
                return {"model_result": final.model_dump(mode="json")}
            if pass_number == 1:
                raise ProposalPlanError("Global proposal review found unresolved issues")
            grouped: dict[str, list[str]] = {}
            valid = {section["name"] for section in sections}
            for issue in issues:
                if not isinstance(issue, dict) or issue.get("section") not in valid or not isinstance(issue.get("instruction"), str):
                    raise ProposalPlanError("Global review referenced an invalid section")
                grouped.setdefault(issue["section"], []).append(issue["instruction"])
            async def revise(name: str, instructions: list[str]) -> tuple[str, str]:
                correction = await generate(base, (
                    f"Revise ONLY the body of section {name!r}. No heading or other sections. "
                    "Preserve approved evidence and avoid unsupported commitments. Correct these global review findings:\n"
                    + "\n".join(f"- {item}" for item in instructions)
                    + "\n\n# Current body\n" + drafts[name]
                ), "proposal.section.revised", {"section": name})
                return name, _section_body(correction.content, name)
            drafts.update(await asyncio.gather(*(revise(name, instructions) for name, instructions in grouped.items())))
        raise AssertionError("Unreachable")

    builder.add_node("plan_proposal", plan)
    builder.add_node("draft_sections", draft)
    builder.add_node("review_sections", review_sections)
    builder.add_node("assemble_proposal", assemble)
    builder.add_node("review_proposal", global_review)
    builder.add_edge("build_context", "plan_proposal")
    builder.add_edge("plan_proposal", "draft_sections")
    builder.add_edge("draft_sections", "review_sections")
    builder.add_edge("review_sections", "assemble_proposal")
    builder.add_edge("assemble_proposal", "review_proposal")
    builder.add_edge("review_proposal", END)
