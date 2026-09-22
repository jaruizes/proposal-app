"""Agent-owned Google Slides materialization through Agent Platform MCP tools.

One business AgentExecution owns the complete presentation materialization. Internal
chunking, LLM calls, MCP tool calls and checkpoints are cognitive/runtime concerns.
"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from langgraph.graph import END, StateGraph

from agent_platform.application.cache import stable_cache_key
from agent_platform.application.models import ModelMessage, ModelProviderError, ModelRequest, ModelResult, ModelRole, ModelUsage
from agent_platform.application.observability import timed_span
from agent_platform.domain import AgentExecutionRequest, CognitiveContext, ToolCall


_ALLOWED_MUTATION_TOOLS = {
    "slides_duplicate_slide",
    "slides_delete_slide",
    "slides_move_slides",
    "slides_replace_text",
    "slides_replace_element_text",
    "slides_batch_update",
}
_MAX_SLIDES_PER_CHUNK = 1
PRESENTATION_MATERIALIZATION_CONTRACT_VERSION = 10


class PresentationMaterializationError(RuntimeError):
    pass


def _extract_marked(text: str, marker: str, next_marker: str | None = None) -> str:
    start = text.find(marker)
    if start < 0:
        return ""
    start += len(marker)
    if next_marker:
        end = text.find(next_marker, start)
        if end >= 0:
            return text[start:end].strip()
    return text[start:].strip()


def _drive_id(value: str | None) -> str:
    raw = (value or "").strip()
    marker = "/folders/"
    if marker in raw:
        rest = raw.split(marker, 1)[1]
        return rest.split("?", 1)[0].split("/", 1)[0]
    return raw


def _presentation_id(value: str | None) -> str:
    raw = (value or "").strip()
    marker = "/presentation/d/"
    if marker in raw:
        rest = raw.split(marker, 1)[1]
        return rest.split("?", 1)[0].split("/", 1)[0]
    return raw


def _compact_text(text_node: Any) -> str:
    if not isinstance(text_node, dict):
        return ""
    parts: list[str] = []
    for element in text_node.get("textElements", []) or []:
        if not isinstance(element, dict):
            continue
        content = ((element.get("textRun") or {}).get("content") or "")
        if content:
            parts.append(str(content))
        if sum(len(part) for part in parts) >= 180:
            break
    value = re.sub(r"\s+", " ", "".join(parts)).strip()
    return value[:180]


def _compact_template(raw: str) -> str:
    try:
        root = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise PresentationMaterializationError("Google Slides template returned invalid JSON") from exc
    out: dict[str, Any] = {
        "presentationId": root.get("presentationId", ""),
        "title": root.get("title", ""),
        "slides": [],
        "layouts": [],
        "masters": [],
        "slideCount": len(root.get("slides", []) or []),
        "layoutCount": len(root.get("layouts", []) or []),
        "masterCount": len(root.get("masters", []) or []),
    }
    for slide in (root.get("slides", []) or [])[:40]:
        compact = {
            "objectId": slide.get("objectId", ""),
            "layoutObjectId": ((slide.get("slideProperties") or {}).get("layoutObjectId") or ""),
            "elements": [],
        }
        for element in (slide.get("pageElements", []) or [])[:12]:
            item = {"objectId": element.get("objectId", "")}
            if "shape" in element:
                item.update({
                    "kind": "shape",
                    "shapeType": (element.get("shape") or {}).get("shapeType", ""),
                    "text": _compact_text((element.get("shape") or {}).get("text") or {}),
                })
            elif "image" in element:
                item["kind"] = "image"
            elif "table" in element:
                item["kind"] = "table"
            elif "line" in element:
                item["kind"] = "line"
            else:
                item["kind"] = "other"
            compact["elements"].append(item)
        out["slides"].append(compact)
    for layout in (root.get("layouts", []) or [])[:30]:
        properties = layout.get("layoutProperties") or {}
        out["layouts"].append({
            "objectId": layout.get("objectId", ""),
            "name": properties.get("name", ""),
            "masterObjectId": properties.get("masterObjectId", ""),
        })
    for master in (root.get("masters", []) or [])[:10]:
        out["masters"].append({"objectId": master.get("objectId", "")})
    value = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    if len(value) > 200_000:
        for slide in out["slides"]:
            slide.pop("elements", None)
        out["elementsOmittedForSize"] = True
        value = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    return value


def _split_slides_plan(slides_plan: str, max_slides: int = _MAX_SLIDES_PER_CHUNK) -> list[str]:
    if not slides_plan.strip():
        return [""]
    title = ""
    section = ""
    current: list[str] = []
    blocks: list[tuple[str, str]] = []

    for line in slides_plan.splitlines():
        if line.startswith("# ") and not line.startswith("# SECTION-") and not title:
            title = line.strip()
            continue
        if line.startswith("# SECTION-"):
            if current:
                blocks.append((section, "\n".join(current).strip()))
                current = []
            section = line.strip()
            continue
        if line.startswith("## SLIDE-"):
            if current:
                blocks.append((section, "\n".join(current).strip()))
                current = []
            current.append(line)
            continue
        if current:
            current.append(line)
    if current:
        blocks.append((section, "\n".join(current).strip()))
    if not blocks:
        return [slides_plan.strip()]

    chunks: list[str] = []
    for offset in range(0, len(blocks), max_slides):
        lines: list[str] = [title] if title else []
        last_section = ""
        for section_name, body in blocks[offset : offset + max_slides]:
            if section_name and section_name != last_section:
                lines.extend(["", section_name])
                last_section = section_name
            lines.extend(["", body])
        chunks.append("\n".join(lines).strip())
    return chunks


def _slides_outline(slides_plan: str) -> str:
    lines = [
        line for line in slides_plan.splitlines()
        if line.startswith("# ") or line.startswith("## SLIDE-")
    ]
    return "\n".join(lines)[:12_000]


def _replace_presentation_id(value: Any, presentation_id: str) -> Any:
    if isinstance(value, str):
        return value.replace("$PRESENTATION_ID", presentation_id)
    if isinstance(value, list):
        return [_replace_presentation_id(item, presentation_id) for item in value]
    if isinstance(value, dict):
        return {str(key): _replace_presentation_id(item, presentation_id) for key, item in value.items()}
    return value


def _validate_operation_arguments(tool: str, arguments: dict[str, Any]) -> None:
    """Validate platform-owned MCP contracts before any external side effect."""
    def require_string(name: str) -> None:
        value = arguments.get(name)
        if not isinstance(value, str) or not value.strip():
            raise PresentationMaterializationError(f"{tool} requires non-empty {name}")

    def require_list(name: str) -> list[Any]:
        value = arguments.get(name)
        if not isinstance(value, list) or not value:
            raise PresentationMaterializationError(f"{tool} requires non-empty {name}[]")
        return value

    if tool in {"slides_duplicate_slide", "slides_delete_slide"}:
        require_string("slideObjectId")
    elif tool == "slides_move_slides":
        slide_ids = require_list("slideObjectIds")
        if not all(isinstance(item, str) and item.strip() for item in slide_ids):
            raise PresentationMaterializationError("slides_move_slides slideObjectIds[] must contain non-empty strings")
        insertion_index = arguments.get("insertionIndex")
        if not isinstance(insertion_index, int) or isinstance(insertion_index, bool) or insertion_index < 0:
            raise PresentationMaterializationError("slides_move_slides requires insertionIndex >= 0")
    elif tool == "slides_replace_text":
        page_ids = require_list("pageObjectIds")
        if not all(isinstance(item, str) and item.strip() for item in page_ids):
            raise PresentationMaterializationError("slides_replace_text pageObjectIds[] must contain non-empty strings")
        replacements = require_list("replacements")
        for replacement in replacements:
            if not isinstance(replacement, dict):
                raise PresentationMaterializationError("slides_replace_text replacements[] must contain objects")
            if not isinstance(replacement.get("from"), str) or not isinstance(replacement.get("to"), str):
                raise PresentationMaterializationError("slides_replace_text replacements[] requires string from/to")
            if not isinstance(replacement.get("matchCase", True), bool):
                raise PresentationMaterializationError("slides_replace_text replacements[].matchCase must be boolean")
    elif tool == "slides_replace_element_text":
        require_string("elementObjectId")
        if not isinstance(arguments.get("text"), str):
            raise PresentationMaterializationError("slides_replace_element_text requires string text")
    elif tool == "slides_batch_update":
        requests = require_list("requests")
        if not all(isinstance(item, dict) and item for item in requests):
            raise PresentationMaterializationError("slides_batch_update requests[] must contain non-empty objects")


def _extract_json_object(content: str) -> dict[str, Any]:
    raw = (content or "").strip()
    if not raw:
        raise PresentationMaterializationError("Presentation materialization returned empty output")
    try:
        value = json.loads(raw)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    if start < 0:
        raise PresentationMaterializationError("Presentation materialization returned invalid JSON")
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(raw)):
        ch = raw[index]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = raw[start:index + 1]
                try:
                    value = json.loads(candidate)
                except json.JSONDecodeError as exc:
                    raise PresentationMaterializationError("Presentation materialization returned invalid JSON") from exc
                if not isinstance(value, dict):
                    raise PresentationMaterializationError("Presentation materialization JSON must be an object")
                return value
    raise PresentationMaterializationError("Presentation materialization returned incomplete JSON")


def _operation_plan(content: str) -> list[dict[str, Any]]:
    value = _extract_json_object(content)
    operations = value.get("operations") if isinstance(value, dict) else None
    if not isinstance(operations, list):
        raise PresentationMaterializationError("Presentation operation plan must contain operations[]")
    normalized: list[dict[str, Any]] = []
    for operation in operations:
        if not isinstance(operation, dict):
            raise PresentationMaterializationError("Invalid presentation operation")
        tool = str(operation.get("tool") or "")
        if tool not in _ALLOWED_MUTATION_TOOLS:
            raise PresentationMaterializationError(f"Presentation operation not allowed: {tool}")
        arguments = operation.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise PresentationMaterializationError(f"Arguments for {tool} must be an object")
        _validate_operation_arguments(tool, arguments)
        normalized.append({"tool": tool, "arguments": arguments})
    return normalized


def _semantic_slide_plan(content: str, template_inventory: str) -> dict[str, Any]:
    value = _extract_json_object(content)
    source_slide_id = str(value.get("templateSlideObjectId") or "").strip()
    elements = value.get("elements")
    if not source_slide_id:
        raise PresentationMaterializationError("Semantic slide plan requires templateSlideObjectId")
    if not isinstance(elements, list):
        raise PresentationMaterializationError("Semantic slide plan requires elements[]")

    try:
        inventory = json.loads(template_inventory)
    except json.JSONDecodeError as exc:
        raise PresentationMaterializationError("Template inventory is invalid JSON") from exc
    slides = inventory.get("slides", []) if isinstance(inventory, dict) else []
    source = next((slide for slide in slides if slide.get("objectId") == source_slide_id), None)
    if source is None:
        raise PresentationMaterializationError(f"Unknown template slide objectId: {source_slide_id}")
    allowed_elements = {
        str(element.get("objectId")): element
        for element in (source.get("elements") or [])
        if isinstance(element, dict) and element.get("objectId")
    }

    normalized_elements: list[dict[str, str]] = []
    seen: set[str] = set()
    for element in elements:
        if not isinstance(element, dict):
            raise PresentationMaterializationError("Semantic slide elements[] must contain objects")
        element_id = str(element.get("templateElementObjectId") or "").strip()
        text = element.get("text")
        if not element_id or element_id not in allowed_elements:
            raise PresentationMaterializationError(f"Unknown template element objectId: {element_id}")
        if allowed_elements[element_id].get("kind") != "shape":
            raise PresentationMaterializationError(f"Template element is not a text shape: {element_id}")
        if not isinstance(text, str):
            raise PresentationMaterializationError(f"Semantic slide element {element_id} requires string text")
        if element_id in seen:
            raise PresentationMaterializationError(f"Duplicate semantic slide element: {element_id}")
        seen.add(element_id)
        normalized_elements.append({"templateElementObjectId": element_id, "text": text})

    text_shape_ids = {
        element_id for element_id, element in allowed_elements.items()
        if element.get("kind") == "shape" and str(element.get("text") or "")
    }
    missing = sorted(text_shape_ids - seen)
    if missing:
        raise PresentationMaterializationError(
            "Semantic slide plan must explicitly map or clear every populated template text shape: "
            + ", ".join(missing)
        )
    return {"templateSlideObjectId": source_slide_id, "elements": normalized_elements}


def _parse_duplicate_result(raw: str) -> tuple[str, dict[str, str]]:
    try:
        node = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PresentationMaterializationError("Slide duplication returned invalid JSON") from exc
    replies = node if isinstance(node, list) else node.get("replies", []) if isinstance(node, dict) else []
    for reply in replies:
        duplicate = reply.get("duplicateObject") if isinstance(reply, dict) else None
        if not isinstance(duplicate, dict):
            continue
        slide_id = str(duplicate.get("objectId") or "").strip()
        mapping_raw = duplicate.get("objectIds") or {}
        mapping = {str(k): str(v) for k, v in mapping_raw.items()} if isinstance(mapping_raw, dict) else {}
        if slide_id:
            return slide_id, mapping
    raise PresentationMaterializationError("Slide duplication returned no duplicated slide objectId")


def _template_slide_ids(template_inventory: str) -> list[str]:
    try:
        inventory = json.loads(template_inventory)
    except json.JSONDecodeError as exc:
        raise PresentationMaterializationError("Template inventory is invalid JSON") from exc
    return [
        str(slide.get("objectId"))
        for slide in (inventory.get("slides", []) if isinstance(inventory, dict) else [])
        if isinstance(slide, dict) and slide.get("objectId")
    ]


async def _validate_registry_operations(runtime, operations: list[dict[str, Any]]) -> None:
    if runtime._tools is None:
        raise PresentationMaterializationError("Agent Platform ToolRegistry is not configured")
    for operation in operations:
        arguments = _replace_presentation_id(operation["arguments"], "$PRESENTATION_ID")
        if "presentationId" not in arguments:
            arguments["presentationId"] = "$PRESENTATION_ID"
        error = await runtime._tools.validate_arguments(operation["tool"], arguments)
        if error is not None:
            raise PresentationMaterializationError(error)


async def _tool_text(runtime, execution, tool_key: str, arguments: dict[str, Any]) -> str:
    if runtime._tools is None:
        raise PresentationMaterializationError("Agent Platform ToolRegistry is not configured")
    result = await runtime._tools.invoke(ToolCall(
        tool_key=tool_key,
        arguments=arguments,
        correlation_id=execution.correlation_id,
        metadata={"execution_id": str(execution.id), "graph": "presentation-materialization"},
    ))
    await runtime._executions.add_event(execution.id, "tool.executed", {
        "tool": tool_key,
        "error": result.is_error,
    })
    if result.is_error:
        message = result.error.message if result.error else f"{tool_key} failed"
        raise PresentationMaterializationError(message)
    if result.structured_content is not None:
        return json.dumps(result.structured_content, ensure_ascii=False)
    parts = [
        str(item.get("text", ""))
        for item in result.content
        if isinstance(item, dict) and item.get("type") == "text"
    ]
    return "\n".join(part for part in parts if part)


def _parse_created_id(raw: str) -> str:
    try:
        node = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PresentationMaterializationError("Google Workspace MCP returned invalid creation JSON") from exc
    presentation_id = str(node.get("id") or node.get("presentationId") or "")
    if not presentation_id:
        raise PresentationMaterializationError("Presentation creation returned no presentation id")
    return presentation_id


def _structural_qa(slides_plan: str, raw_structure: str) -> str:
    expected = sum(1 for line in slides_plan.splitlines() if line.startswith("## SLIDE-"))
    try:
        root = json.loads(raw_structure)
    except json.JSONDecodeError:
        return f"WARN expectedSlides={expected}, final structure was not parseable"
    slides = root.get("slides", []) or []
    leftovers = 0
    for slide in slides:
        for element in slide.get("pageElements", []) or []:
            shape = element.get("shape") or {}
            text = _compact_text(shape.get("text") or {}).lower()
            if any(token in text for token in ("lorem ipsum", "placeholder", "insert text")):
                leftovers += 1
    actual = len(slides)
    if actual != expected:
        return f"WARN expectedSlides={expected}, actualSlides={actual}, templateLeftovers={leftovers}"
    if leftovers:
        return f"WARN templateLeftovers={leftovers}"
    return f"OK expectedSlides={expected}, actualSlides={actual}"


def add_presentation_materialization_nodes(builder: StateGraph, runtime, execution) -> None:
    calls: list[ModelResult] = []

    async def base_request(state: dict) -> ModelRequest:
        request = AgentExecutionRequest.model_validate(state["request"])
        context = CognitiveContext.model_validate(state["cognitive_context"])
        agent = await runtime._agents.get(request.agent_key)
        skill = await runtime._skills.get(request.skill_key)
        assembled = runtime._prompt_assembler.build(agent, skill, request, context)
        return assembled.model_copy(update={
            "messages": [ModelMessage(role=ModelRole.USER, content=f"# Task\n{request.objective}")],
            "cache_system_prompt": True,
        })

    async def generate_json(base: ModelRequest, instruction: str, stage: str, max_output_tokens: int = 4500) -> ModelResult:
        checkpoint = stable_cache_key({
            "version": PRESENTATION_MATERIALIZATION_CONTRACT_VERSION,
            "stage": stage,
            "model": base.model,
            "instruction": instruction,
        })
        if runtime._cache is not None:
            cached = await runtime._cache.get_json("presentation-materialization-step", checkpoint)
            if cached is not None:
                cached_result = ModelResult.model_validate(cached)
                try:
                    cached_operations = _operation_plan(cached_result.content)
                    await _validate_registry_operations(runtime, cached_operations)
                except PresentationMaterializationError:
                    await runtime._executions.add_event(execution.id, "presentation.materialization.step.cache_rejected", {
                        "stage": stage,
                        "reason": "invalid_tool_contract",
                    })
                else:
                    await runtime._executions.add_event(execution.id, "presentation.materialization.step.reused", {"stage": stage})
                    return cached_result.model_copy(update={
                        "usage": ModelUsage(),
                        "provider_request_id": None,
                        "metadata": {"checkpoint_hit": True},
                    })

        factors = (1.0, 1.0, 1.0)
        last_error = "unknown"
        for attempt, factor in enumerate(factors, start=1):
            limit = max(900, int(max_output_tokens * factor))
            retry = "" if attempt == 1 else (
                "\n\n# RETRY AFTER OUTPUT FAILURE\n"
                f"Previous attempt failed ({last_error}). Return ONLY one complete JSON object. "
                f"Use at most {max(250, int(limit * .30))} words/tokens-equivalent. "
                "No markdown, prose, comments or operations outside the assigned slides."
            )
            request = base.model_copy(update={
                "messages": [ModelMessage(role=ModelRole.USER, content=instruction + retry)],
                "max_output_tokens": limit,
            })
            try:
                with timed_span("langgraph.presentation-materialization.model", stage=stage, attempt=attempt):
                    result = await runtime._model_provider.generate(request)
                operations = _operation_plan(result.content)
                await _validate_registry_operations(runtime, operations)
                calls.append(result)
                if runtime._cache is not None:
                    await runtime._cache.set_json(
                        "presentation-materialization-step",
                        checkpoint,
                        result.model_dump(mode="json"),
                        ttl_seconds=604800,
                    )
                await runtime._executions.add_event(execution.id, "presentation.materialization.step.completed", {
                    "stage": stage,
                    "attempt": attempt,
                    "output_tokens": result.usage.output_tokens,
                })
                return result
            except ModelProviderError as exc:
                if exc.code != "ANTHROPIC_OUTPUT_TRUNCATED" or attempt == len(factors):
                    raise
                last_error = exc.code
            except PresentationMaterializationError as exc:
                if attempt == len(factors):
                    raise
                last_error = str(exc)[:1200] or "INVALID_AGENT_OUTPUT"
        raise AssertionError("unreachable")

    async def generate_semantic_json(base: ModelRequest, instruction: str, stage: str, template_inventory: str) -> ModelResult:
        checkpoint = stable_cache_key({
            "version": PRESENTATION_MATERIALIZATION_CONTRACT_VERSION,
            "stage": stage,
            "model": base.model,
            "instruction": instruction,
            "mode": "semantic-template-slide",
        })
        if runtime._cache is not None:
            cached = await runtime._cache.get_json("presentation-materialization-step", checkpoint)
            if cached is not None:
                cached_result = ModelResult.model_validate(cached)
                try:
                    _semantic_slide_plan(cached_result.content, template_inventory)
                except PresentationMaterializationError:
                    await runtime._executions.add_event(execution.id, "presentation.materialization.step.cache_rejected", {
                        "stage": stage,
                        "reason": "invalid_semantic_slide_plan",
                    })
                else:
                    return cached_result.model_copy(update={
                        "usage": ModelUsage(),
                        "provider_request_id": None,
                        "metadata": {"checkpoint_hit": True},
                    })

        last_error = "unknown"
        for attempt in range(1, 4):
            retry = "" if attempt == 1 else (
                "\n\n# RETRY AFTER OUTPUT FAILURE\n"
                f"Previous attempt failed ({last_error}). Return ONLY the semantic JSON object. "
                "Do not emit Google Slides API requests, synthetic object IDs, markdown or prose."
            )
            request = base.model_copy(update={
                "messages": [ModelMessage(role=ModelRole.USER, content=instruction + retry)],
                "max_output_tokens": 2200,
            })
            try:
                with timed_span("langgraph.presentation-materialization.semantic-model", stage=stage, attempt=attempt):
                    result = await runtime._model_provider.generate(request)
                _semantic_slide_plan(result.content, template_inventory)
                calls.append(result)
                if runtime._cache is not None:
                    await runtime._cache.set_json(
                        "presentation-materialization-step", checkpoint,
                        result.model_dump(mode="json"), ttl_seconds=604800,
                    )
                return result
            except ModelProviderError as exc:
                if exc.code != "ANTHROPIC_OUTPUT_TRUNCATED" or attempt == 3:
                    raise
                last_error = exc.code
            except PresentationMaterializationError as exc:
                if attempt == 3:
                    raise
                last_error = str(exc)[:1200] or "INVALID_SEMANTIC_SLIDE_PLAN"
        raise AssertionError("unreachable")

    async def prepare(state: dict) -> dict:
        request = AgentExecutionRequest.model_validate(state["request"])
        business_context = str(request.context.get("business_context") or "")
        slides_plan = _extract_marked(
            business_context,
            "# APPROVED SLIDES PLAN",
            "# PRESENTATION MATERIALIZATION CONFIG JSON",
        )
        config_raw = _extract_marked(business_context, "# PRESENTATION MATERIALIZATION CONFIG JSON")
        if not slides_plan:
            raise PresentationMaterializationError("Approved slides-plan is missing from execution context")
        try:
            config = json.loads(config_raw)
        except json.JSONDecodeError as exc:
            raise PresentationMaterializationError("Presentation materialization config is invalid JSON") from exc

        template_id = _presentation_id(str(config.get("templateId") or ""))
        template_raw = "{\"slides\":[],\"layouts\":[],\"masters\":[]}"
        if template_id:
            template_raw = await _tool_text(runtime, execution, "slides_get_presentation", {"presentationId": template_id})
        template_inventory = _compact_template(template_raw)
        chunks = _split_slides_plan(slides_plan)

        await runtime._executions.add_event(execution.id, "presentation.materialization.prepared", {
            "slides": sum(1 for line in slides_plan.splitlines() if line.startswith("## SLIDE-")),
            "chunks": len(chunks),
            "template": bool(template_id),
        })
        return {
            "presentation_materialization": {
                "slides_plan": slides_plan,
                "config": config,
                "template_id": template_id,
                "template_inventory": template_inventory,
                "chunks": chunks,
                "outline": _slides_outline(slides_plan),
            }
        }

    async def plan(state: dict) -> dict:
        data = state["presentation_materialization"]
        base = await base_request(state)
        chunks = data["chunks"]
        plans: list[str] = []

        if data["template_id"]:
            for index, chunk in enumerate(chunks, start=1):
                instruction = (
                    "Return ONLY JSON with this exact shape: "
                    "{\"templateSlideObjectId\":\"EXISTING_TEMPLATE_SLIDE_ID\","
                    "\"elements\":[{\"templateElementObjectId\":\"EXISTING_TEMPLATE_ELEMENT_ID\",\"text\":\"final visible text\"}]}.\n"
                    "This is a semantic rendering plan, NOT a Google Slides API plan. "
                    "Choose exactly one EXISTING slide objectId from the compact template inventory. "
                    "Use ONLY element objectIds that belong to that chosen template slide. "
                    "Never invent object IDs. Never emit createSlide, duplicateObject, replaceAllText, batchUpdate or any MCP tool. "
                    "For every populated text shape in the chosen template slide, include an elements[] entry: "
                    "set its final approved text, or set text to empty string to clear unused template/example copy. "
                    "Preserve the approved slide title and narrative wording exactly; only map it onto the corporate pattern.\n\n"
                    f"# GLOBAL OUTLINE\n{data['outline']}\n\n"
                    f"# CURRENT APPROVED SLIDE {index}/{len(chunks)}\n{chunk}\n\n"
                    f"# COMPACT TEMPLATE INVENTORY\n{data['template_inventory']}"
                )
                result = await generate_semantic_json(
                    base, instruction, f"presentation.materialization.semantic.{index}", data["template_inventory"]
                )
                plans.append(result.content)
            updated = dict(data)
            updated["semantic_plans"] = plans
            updated["materialization_mode"] = "semantic-template"
            return {"presentation_materialization": updated}

        # Blank-presentation fallback remains supported, but template-based materialization
        # never exposes low-level Google Slides requests to the model.
        for index, chunk in enumerate(chunks, start=1):
            instruction = (
                "Produce ONLY JSON {\"operations\":[{\"tool\":\"slides_batch_update\",\"arguments\":{...}}]}.\n"
                "Materialize ONLY this slide into a blank presentation. Use $PRESENTATION_ID as presentationId. "
                "Do not modify any other slide. Prefer one compact batchUpdate request.\n\n"
                f"# CURRENT CHUNK {index}/{len(chunks)}\n{chunk}"
            )
            result = await generate_json(base, instruction, f"presentation.materialization.blank.{index}")
            plans.append(result.content)
        updated = dict(data)
        updated["operation_plans"] = plans
        updated["materialization_mode"] = "blank-low-level"
        return {"presentation_materialization": updated}

    async def materialize(state: dict) -> dict:
        data = state["presentation_materialization"]
        config = data["config"]
        template_id = data["template_id"]
        folder_id = _drive_id(str(config.get("outputFolder") or ""))
        document_name = str(config.get("presentationName") or "Generated presentation").strip()

        if template_id:
            semantic_plans = [
                _semantic_slide_plan(raw_plan, data["template_inventory"])
                for raw_plan in data.get("semantic_plans", [])
            ]
            if len(semantic_plans) != len(data["chunks"]):
                raise PresentationMaterializationError("Semantic materialization did not produce one plan per approved slide")
            args: dict[str, Any] = {"fileId": template_id, "newName": document_name}
            if folder_id:
                args["destinationFolderId"] = folder_id
            created = await _tool_text(runtime, execution, "drive_copy_file", args)
            presentation_id = _parse_created_id(created)

            generated_slide_ids: list[str] = []
            operation_count = 0
            for plan_index, plan in enumerate(semantic_plans, start=1):
                duplicate_raw = await _tool_text(runtime, execution, "slides_duplicate_slide", {
                    "presentationId": presentation_id,
                    "slideObjectId": plan["templateSlideObjectId"],
                })
                duplicated_slide_id, object_id_map = _parse_duplicate_result(duplicate_raw)
                generated_slide_ids.append(duplicated_slide_id)
                operation_count += 1

                for element in plan["elements"]:
                    template_element_id = element["templateElementObjectId"]
                    duplicated_element_id = object_id_map.get(template_element_id)
                    if not duplicated_element_id:
                        raise PresentationMaterializationError(
                            f"Google Slides duplication did not map template element {template_element_id} "
                            f"for semantic slide {plan_index}"
                        )
                    await _tool_text(runtime, execution, "slides_replace_element_text", {
                        "presentationId": presentation_id,
                        "elementObjectId": duplicated_element_id,
                        "text": element["text"],
                    })
                    operation_count += 1

            # Remove template/sample slides only after every target slide exists. This keeps
            # source IDs valid throughout materialization and avoids synthetic cross-request IDs.
            for original_slide_id in _template_slide_ids(data["template_inventory"]):
                await _tool_text(runtime, execution, "slides_delete_slide", {
                    "presentationId": presentation_id,
                    "slideObjectId": original_slide_id,
                })
                operation_count += 1

            if generated_slide_ids:
                await _tool_text(runtime, execution, "slides_move_slides", {
                    "presentationId": presentation_id,
                    "slideObjectIds": generated_slide_ids,
                    "insertionIndex": 0,
                })
                operation_count += 1
        else:
            validated_plans = [_operation_plan(raw_plan) for raw_plan in data.get("operation_plans", [])]
            for operations in validated_plans:
                await _validate_registry_operations(runtime, operations)
            created = await _tool_text(runtime, execution, "slides_create_presentation", {"title": document_name})
            presentation_id = _parse_created_id(created)
            if folder_id:
                await _tool_text(runtime, execution, "drive_move_file", {
                    "fileId": presentation_id,
                    "destinationFolderId": folder_id,
                })
            operation_count = 0
            for operations in validated_plans:
                for operation in operations:
                    arguments = _replace_presentation_id(operation["arguments"], presentation_id)
                    if "presentationId" not in arguments:
                        arguments["presentationId"] = presentation_id
                    await _tool_text(runtime, execution, operation["tool"], arguments)
                    operation_count += 1

        final_structure = await _tool_text(runtime, execution, "slides_get_presentation", {
            "presentationId": presentation_id,
        })
        qa = _structural_qa(data["slides_plan"], final_structure)
        url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"
        compact_structure = _compact_template(final_structure)

        usage = ModelUsage(
            input_tokens=sum(call.usage.input_tokens for call in calls),
            output_tokens=sum(call.usage.output_tokens for call in calls),
            cache_read_tokens=sum(call.usage.cache_read_tokens for call in calls),
            cache_write_tokens=sum(call.usage.cache_write_tokens for call in calls),
        )
        last = calls[-1] if calls else None
        output = {
            "externalId": presentation_id,
            "url": url,
            "buildReport": {
                "templateId": template_id or None,
                "renderingMode": "semantic-corporate-template" if template_id else "blank",
                "operationCount": operation_count,
                "chunks": len(data["chunks"]),
                "structuralQa": qa,
                "finalStructure": json.loads(compact_structure),
            },
        }
        result = ModelResult(
            content=json.dumps(output, ensure_ascii=False),
            model=last.model if last else (AgentExecutionRequest.model_validate(state["request"]).model or "tool-only"),
            usage=usage,
            provider_request_id=last.provider_request_id if last else None,
            metadata={
                "presentation_id": presentation_id,
                "presentation_url": url,
                "materialization_chunks": len(data["chunks"]),
                "mcp_owned_by_agent_platform": True,
                "materialization_contract_version": PRESENTATION_MATERIALIZATION_CONTRACT_VERSION,
                "materialization_mode": data.get("materialization_mode"),
                "llm_generates_raw_google_requests": False if template_id else True,
            },
        )
        await runtime._executions.add_event(execution.id, "presentation.materialization.completed", {
            "presentation_id": presentation_id,
            "url": url,
            "operations": operation_count,
            "chunks": len(data["chunks"]),
            "structural_qa": qa,
            "mode": data.get("materialization_mode"),
        })
        return {"model_result": result.model_dump(mode="json")}

    builder.add_node("presentation_materialization_prepare", prepare)
    builder.add_node("presentation_materialization_plan", plan)
    builder.add_node("presentation_materialization_apply", materialize)
    builder.add_edge("build_context", "presentation_materialization_prepare")
    builder.add_edge("presentation_materialization_prepare", "presentation_materialization_plan")
    builder.add_edge("presentation_materialization_plan", "presentation_materialization_apply")
    builder.add_edge("presentation_materialization_apply", END)


__all__ = [
    "add_presentation_materialization_nodes",
    "_split_slides_plan",
    "_compact_template",
    "_extract_json_object",
    "PRESENTATION_MATERIALIZATION_CONTRACT_VERSION",
]
