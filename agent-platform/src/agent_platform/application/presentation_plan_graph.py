"""Adaptive LangGraph workflow for slides-plan.md generation.

The Business Analyst remains the single cognitive owner. Small proposals are handled
in one model call. Large proposals use an internal storyline + bounded section-detail
workflow and deterministic Markdown assembly.
"""
from __future__ import annotations

import json
import re
from typing import Any

from langgraph.graph import END, StateGraph

from agent_platform.application.cache import stable_cache_key
from agent_platform.application.models import (
    ModelMessage,
    ModelProviderError,
    ModelRequest,
    ModelResult,
    ModelRole,
    ModelUsage,
)
from agent_platform.application.observability import timed_span
from agent_platform.domain import AgentExecutionRequest, CognitiveContext


class PresentationPlanError(ValueError):
    pass


_MAX_SINGLE_CONTEXT_CHARS = 45_000
_MAX_SLIDES = 30
_MAX_SLIDES_PER_SECTION = 5


def _json_object(content: str, label: str) -> dict[str, Any]:
    raw = content.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw).strip()
    try:
        value = json.loads(raw)
    except ValueError as exc:
        raise PresentationPlanError(f"{label} returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise PresentationPlanError(f"{label} must return a JSON object")
    return value


def _canonical_markdown(title: str, sections: list[dict[str, Any]], details: dict[str, list[dict[str, str]]]) -> str:
    chunks = [f"# {title.strip() or 'Hilo de presentación'}"]
    seen_slides: set[str] = set()
    for section in sections:
        section_id = section["id"]
        section_title = section["title"]
        chunks.append(f"# {section_id} — {section_title}")
        section_details = details.get(section_id, [])
        if not section_details:
            raise PresentationPlanError(f"Presentation section {section_id} has no slides")
        for slide in section_details:
            slide_id = slide["id"]
            if slide_id in seen_slides:
                raise PresentationPlanError(f"Duplicate slide id {slide_id}")
            seen_slides.add(slide_id)
            chunks.extend([
                f"## {slide_id}",
                "### Título de slide",
                slide["title"].strip(),
                "### Propósito / mensaje principal",
                slide["purpose"].strip(),
                "### Contenido",
                slide["content"].strip(),
                "### Intención visual",
                slide["visual"].strip(),
                "### Fuentes / trazabilidad",
                slide["sources"].strip() or "proposal.md",
            ])
    return "\n\n".join(chunks).strip() + "\n"


def _validate_outline(value: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    title = str(value.get("title") or "Hilo de presentación").strip()
    raw_sections = value.get("sections")
    if not isinstance(raw_sections, list) or not raw_sections:
        raise PresentationPlanError("Presentation storyline must contain sections")

    prepared: list[tuple[str, list[dict[str, str]]]] = []
    total = 0

    for raw in raw_sections:
        if not isinstance(raw, dict):
            raise PresentationPlanError("Invalid presentation section")
        section_title = str(raw.get("title") or "").strip()
        raw_slides = raw.get("slides")
        if not section_title or not isinstance(raw_slides, list) or not raw_slides:
            raise PresentationPlanError("Invalid presentation section")

        normalized_slides: list[dict[str, str]] = []
        for raw_slide in raw_slides:
            if not isinstance(raw_slide, dict):
                raise PresentationPlanError(f"Invalid slide in section {section_title!r}")
            title_value = str(raw_slide.get("title") or "").strip()
            purpose = str(raw_slide.get("purpose") or "").strip()
            if not title_value or not purpose:
                raise PresentationPlanError(
                    f"Slide in section {section_title!r} is missing title or purpose"
                )
            if len(title_value.split()) > 12:
                # Keep the plan usable instead of failing on a stylistic overflow.
                title_value = " ".join(title_value.split()[:12])
            total += 1
            normalized_slides.append({
                "id": f"SLIDE-{total}",
                "title": title_value,
                "purpose": purpose,
            })

        # A section-size limit is a layout normalization concern, not a fatal
        # semantic validation error. Split oversized sections deterministically
        # without another model call and preserve slide order.
        for offset in range(0, len(normalized_slides), _MAX_SLIDES_PER_SECTION):
            chunk = normalized_slides[offset:offset + _MAX_SLIDES_PER_SECTION]
            suffix = "" if offset == 0 else f" (continuación {offset // _MAX_SLIDES_PER_SECTION + 1})"
            prepared.append((section_title + suffix, chunk))

    if total > _MAX_SLIDES:
        raise PresentationPlanError(
            f"Presentation storyline exceeds the absolute maximum of {_MAX_SLIDES} slides"
        )

    sections: list[dict[str, Any]] = []
    for index, (section_title, slides) in enumerate(prepared, start=1):
        sections.append({
            "id": f"SECTION-{index}",
            "title": section_title,
            "slides": slides,
        })
    return title, sections


def _validate_section_details(section: dict[str, Any], value: dict[str, Any]) -> list[dict[str, str]]:
    raw_slides = value.get("slides")
    if not isinstance(raw_slides, list):
        raise PresentationPlanError(f"{section['id']} detail must contain slides")
    expected = section["slides"]
    if len(raw_slides) != len(expected):
        raise PresentationPlanError(f"{section['id']} detail does not match storyline slide count")
    result: list[dict[str, str]] = []
    for expected_slide, raw in zip(expected, raw_slides):
        if not isinstance(raw, dict):
            raise PresentationPlanError(f"Invalid slide detail in {section['id']}")
        # The storyline is frozen authority. Detail calls are allowed to echo ids/titles
        # imperfectly; normalize them rather than failing a complete phase.
        slide_id = expected_slide["id"]
        title = expected_slide["title"]
        purpose = str(raw.get("purpose") or expected_slide["purpose"]).strip()
        content = str(raw.get("content") or "").strip()
        visual = str(raw.get("visual") or "").strip()
        sources = str(raw.get("sources") or "proposal.md").strip()
        if not content or not visual:
            raise PresentationPlanError(f"Slide {slide_id} is missing content or visual intent")
        result.append({
            "id": slide_id,
            "title": title,
            "purpose": purpose,
            "content": content,
            "visual": visual,
            "sources": sources,
        })
    return result


def add_presentation_plan_nodes(builder: StateGraph, runtime, execution) -> None:
    calls: list[ModelResult] = []

    async def event(name: str, payload: dict[str, Any]) -> None:
        await runtime._executions.add_event(execution.id, name, payload)

    async def base_request(state: dict) -> ModelRequest:
        request = AgentExecutionRequest.model_validate(state["request"])
        context = CognitiveContext.model_validate(state["cognitive_context"])
        agent = await runtime._agents.get(request.agent_key)
        skill = await runtime._skills.get(request.skill_key)
        assembled = runtime._prompt_assembler.build(agent, skill, request, context)
        # The approved proposal and reference snippets are stable across internal calls.
        # Put them in an Anthropic-cacheable block and keep each current stage small.
        return assembled.model_copy(update={
            "messages": [ModelMessage(role=ModelRole.USER, content=f"# Task\n{request.objective}")],
            "cache_system_prompt": True,
            "cacheable_context": assembled.messages[0].content,
        })

    async def generate(
        base: ModelRequest,
        instruction: str,
        stage: str,
        *,
        max_output_tokens: int,
        retry_compact: bool = True,
    ) -> ModelResult:
        cache_key = stable_cache_key({
            "version": 1,
            "stage": stage,
            "model": base.model,
            "system_prompt": base.system_prompt,
            "cacheable_context": base.cacheable_context,
            "instruction": instruction,
            "max_output_tokens": max_output_tokens,
        })
        if runtime._cache is not None:
            cached = await runtime._cache.get_json("presentation-plan-step", cache_key)
            if cached is not None:
                result = ModelResult.model_validate(cached).model_copy(update={
                    "usage": ModelUsage(),
                    "provider_request_id": None,
                    "metadata": {"presentation_plan_checkpoint_hit": True},
                })
                await event("presentation.plan.step.reused", {"stage": stage})
                return result

        attempts = 2 if retry_compact else 1
        for attempt in range(attempts):
            limit = max_output_tokens if attempt == 0 else max(900, int(max_output_tokens * 0.55))
            suffix = "" if attempt == 0 else (
                "\n\n# RETRY AFTER OUTPUT LIMIT\n"
                "Regenerate from scratch much more concisely. Use terse JSON values, short bullets and no prose outside "
                "the requested structure. Do not add slides or sections."
            )
            request = base.model_copy(update={
                "messages": [ModelMessage(role=ModelRole.USER, content=instruction + suffix)],
                "max_output_tokens": limit,
            })
            try:
                with timed_span("langgraph.presentation-plan.model", stage=stage, model=base.model or "default"):
                    result = await runtime._model_provider.generate(request)
                calls.append(result)
                if runtime._cache is not None:
                    await runtime._cache.set_json(
                        "presentation-plan-step", cache_key, result.model_dump(mode="json"), ttl_seconds=86400
                    )
                await event("presentation.plan.step.completed", {
                    "stage": stage,
                    "attempt": attempt + 1,
                    "max_output_tokens": limit,
                    "output_tokens": result.usage.output_tokens,
                })
                return result
            except ModelProviderError as exc:
                if getattr(exc, "code", None) != "ANTHROPIC_OUTPUT_TRUNCATED" or attempt == attempts - 1:
                    raise
                await event("presentation.plan.step.retry", {
                    "stage": stage,
                    "reason": "output_truncated",
                    "next_max_output_tokens": max(900, int(max_output_tokens * 0.55)),
                })
        raise AssertionError("unreachable")

    async def route(state: dict) -> dict:
        request = AgentExecutionRequest.model_validate(state["request"])
        context = request.context.get("business_context", "")
        mode = "SPLIT" if isinstance(context, str) and len(context) > _MAX_SINGLE_CONTEXT_CHARS else "SINGLE"
        await event("presentation.plan.mode", {"mode": mode, "context_chars": len(context) if isinstance(context, str) else 0})
        return {"presentation_plan_mode": mode}

    def after_route(state: dict) -> str:
        return "single" if state.get("presentation_plan_mode") == "SINGLE" else "split"

    async def single(state: dict) -> dict:
        base = await base_request(state)
        instruction = (
            "Create the complete canonical slides-plan.md from the APPROVED proposal. Return raw Markdown only. "
            "Create a presentation narrative, not a proposal transcription. Keep it to at most 24 slides unless the "
            "human guidance explicitly requires fewer. Use this exact structure:\n"
            "# <presentation title>\n"
            "# SECTION-1 — <section title>\n"
            "## SLIDE-1\n"
            "### Título de slide\n<maximum 12 words>\n"
            "### Propósito / mensaje principal\n<one concise message>\n"
            "### Contenido\n<concise slide-ready bullets, normally <= 70 words>\n"
            "### Intención visual\n<one visual/layout direction>\n"
            "### Fuentes / trazabilidad\n<proposal.md section or reference>\n"
            "Repeat sequential SECTION-n and SLIDE-n identifiers. Never use generic cliente/customer wording in visible "
            "slide copy. Do not invent facts, commitments, dates, estimates or technologies."
        )
        try:
            result = await generate(base, instruction, "presentation.plan.single", max_output_tokens=8000, retry_compact=False)
            content = result.content.strip()
            # The Spring validator performs the authoritative final validation. Here only
            # detect obvious truncation/structural incompleteness and fall back to split mode.
            if "# SECTION-" not in content or "### Título de slide" not in content:
                await event("presentation.plan.single.fallback", {"reason": "incomplete_structure"})
                return {"presentation_plan_force_split": True}
            return {"model_result": result.model_dump(mode="json"), "presentation_plan_force_split": False}
        except ModelProviderError as exc:
            if getattr(exc, "code", None) == "ANTHROPIC_OUTPUT_TRUNCATED":
                await event("presentation.plan.single.fallback", {"reason": "output_truncated"})
                return {"presentation_plan_force_split": True}
            raise

    def after_single(state: dict) -> str:
        return "split" if state.get("presentation_plan_force_split") else "done"

    async def outline(state: dict) -> dict:
        base = await base_request(state)
        result = await generate(
            base,
            (
                "Design ONLY the presentation storyline from the approved proposal and human presentation guidance. "
                "Return ONLY JSON: {\"title\":\"...\",\"sections\":[{\"title\":\"...\","
                "\"slides\":[{\"title\":\"max 12 words\",\"purpose\":\"one concise primary message\"}]}]}. "
                "Use 10-24 slides for a substantial proposal, fewer when appropriate, never more than 30. "
                "Maximum 5 slides per section. Titles must be specific and customer-facing; never use generic "
                "cliente/customer wording. Cover context/value, proposed solution, architecture where material, delivery, "
                "risk/governance and next steps without repeating the proposal."
            ),
            "presentation.plan.outline",
            max_output_tokens=3200,
        )
        value = _json_object(result.content, "Presentation storyline")
        title, sections = _validate_outline(value)
        await event("presentation.plan.outline.completed", {
            "sections": len(sections),
            "slides": sum(len(section["slides"]) for section in sections),
        })
        return {"presentation_plan_title": title, "presentation_plan_sections": sections}

    async def details(state: dict) -> dict:
        base = await base_request(state)
        all_details: dict[str, list[dict[str, str]]] = {}
        for section in state["presentation_plan_sections"]:
            frozen = json.dumps(section, ensure_ascii=False, separators=(",", ":"))
            result = await generate(
                base,
                (
                    "Complete ONLY the slide details for this frozen storyline section. Return ONLY JSON "
                    "{\"slides\":[{\"id\":\"SLIDE-n\",\"title\":\"exact frozen title\","
                    "\"purpose\":\"...\",\"content\":\"concise slide-ready bullets/text <= 70 words\","
                    "\"visual\":\"one concrete visual/layout intent\",\"sources\":\"proposal.md traceability\"}]}. "
                    "Do not change ids, titles, slide count or order. Do not invent facts. Never use generic "
                    "cliente/customer wording in visible content.\n\n# FROZEN STORYLINE SECTION\n" + frozen
                ),
                f"presentation.plan.section.{section['id']}",
                max_output_tokens=3000,
            )
            all_details[section["id"]] = _validate_section_details(
                section, _json_object(result.content, section["id"])
            )
        markdown = _canonical_markdown(
            state["presentation_plan_title"], state["presentation_plan_sections"], all_details
        )
        usage = ModelUsage(
            input_tokens=sum(call.usage.input_tokens for call in calls),
            output_tokens=sum(call.usage.output_tokens for call in calls),
            cache_read_tokens=sum(call.usage.cache_read_tokens for call in calls),
            cache_write_tokens=sum(call.usage.cache_write_tokens for call in calls),
        )
        last = calls[-1]
        final = ModelResult(
            content=markdown,
            model=last.model,
            usage=usage,
            provider_request_id=last.provider_request_id,
            metadata={
                "presentation_plan_mode": "SPLIT",
                "presentation_plan_model_calls": len(calls),
                "presentation_plan_sections": len(state["presentation_plan_sections"]),
                "presentation_plan_slides": sum(len(s["slides"]) for s in state["presentation_plan_sections"]),
            },
        )
        return {"model_result": final.model_dump(mode="json")}

    builder.add_node("presentation_plan_route", route)
    builder.add_node("presentation_plan_single", single)
    builder.add_node("presentation_plan_outline", outline)
    builder.add_node("presentation_plan_details", details)
    builder.add_edge("build_context", "presentation_plan_route")
    builder.add_conditional_edges(
        "presentation_plan_route",
        after_route,
        {"single": "presentation_plan_single", "split": "presentation_plan_outline"},
    )
    builder.add_conditional_edges(
        "presentation_plan_single",
        after_single,
        {"done": END, "split": "presentation_plan_outline"},
    )
    builder.add_edge("presentation_plan_outline", "presentation_plan_details")
    builder.add_edge("presentation_plan_details", END)
