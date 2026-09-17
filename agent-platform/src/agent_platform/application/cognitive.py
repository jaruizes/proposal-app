from __future__ import annotations

import asyncio
import json
from typing import Protocol

from agent_platform.domain import (
    AgentDefinition,
    AgentExecutionRequest,
    CognitiveContext,
    CognitiveContextItem,
    CognitiveSection,
    EpistemicLabel,
    SkillDefinition,
)


class ContextContributor(Protocol):
    """Extension point for memory, RAG, graph, enterprise data and other context sources."""

    name: str
    required: bool

    async def contribute(
        self,
        agent: AgentDefinition,
        skill: SkillDefinition | None,
        request: AgentExecutionRequest,
    ) -> list[CognitiveContextItem]: ...


class ApplicationContextContributor:
    name = "application-context"
    required = True

    async def contribute(self, agent, skill, request) -> list[CognitiveContextItem]:
        if not request.context:
            return []
        return [
            CognitiveContextItem(
                key="application-context",
                section=CognitiveSection.BUSINESS_CONTEXT,
                content=request.context,
                source=self.name,
                priority=100,
                required=True,
            )
        ]


class AttachmentContextContributor:
    name = "attachments"
    required = True

    async def contribute(self, agent, skill, request) -> list[CognitiveContextItem]:
        items: list[CognitiveContextItem] = []
        for index, attachment in enumerate(request.attachments):
            items.append(
                CognitiveContextItem(
                    key=f"attachment:{index}:{attachment.name}",
                    section=CognitiveSection.SOURCE_MATERIAL,
                    content={
                        "name": attachment.name,
                        "media_type": attachment.media_type,
                        "uri": attachment.uri,
                        "content": attachment.content,
                    },
                    source=self.name,
                    priority=95,
                    required=True,
                    metadata=attachment.metadata,
                )
            )
        return items


class CognitiveContextPolicy:
    """Simple deterministic budget until tokenizer-aware context planning is introduced."""

    def __init__(self, *, max_items: int = 50, max_context_chars: int = 80_000) -> None:
        self.max_items = max_items
        self.max_context_chars = max_context_chars


class CognitiveContextBuilder:
    """Builds one bounded cognitive envelope without coupling the runtime to RAG or memory implementations."""

    def __init__(
        self,
        contributors: list[ContextContributor] | None = None,
        policy: CognitiveContextPolicy | None = None,
    ) -> None:
        self._contributors = contributors or [ApplicationContextContributor(), AttachmentContextContributor()]
        self._policy = policy or CognitiveContextPolicy()

    async def build(
        self,
        agent: AgentDefinition,
        skill: SkillDefinition | None,
        request: AgentExecutionRequest,
    ) -> CognitiveContext:
        warnings: list[str] = []

        async def run(contributor: ContextContributor) -> list[CognitiveContextItem]:
            try:
                return await contributor.contribute(agent, skill, request)
            except Exception as exc:
                if contributor.required:
                    raise
                warnings.append(f"{contributor.name}: {str(exc) or type(exc).__name__}")
                return []

        groups = await asyncio.gather(*(run(contributor) for contributor in self._contributors))
        candidates = [item for group in groups for item in group]
        selected, dropped = self._apply_budget(candidates)

        skill_tools = skill.allowed_tools if skill else []
        if skill_tools and agent.allowed_tools:
            allowed_tools = [tool for tool in skill_tools if tool in set(agent.allowed_tools)]
        elif skill_tools:
            allowed_tools = list(skill_tools)
        else:
            allowed_tools = list(agent.allowed_tools)

        return CognitiveContext(
            items=selected,
            knowledge_sources=list(skill.knowledge_sources if skill else []),
            knowledge_scopes=list(agent.knowledge_scopes),
            allowed_tools=allowed_tools,
            warnings=warnings,
            dropped_items=dropped,
            metadata={
                "agent_key": agent.key,
                "agent_version": agent.version,
                "skill_key": skill.key if skill else None,
                "skill_version": skill.version if skill else None,
                "contributors": [contributor.name for contributor in self._contributors],
                "budget": {
                    "max_items": self._policy.max_items,
                    "max_context_chars": self._policy.max_context_chars,
                },
            },
        )

    def _apply_budget(
        self, items: list[CognitiveContextItem]
    ) -> tuple[list[CognitiveContextItem], list[str]]:
        indexed = list(enumerate(items))
        indexed.sort(key=lambda pair: (-pair[1].priority, pair[0]))
        selected: list[tuple[int, CognitiveContextItem]] = []
        dropped: list[str] = []
        used_chars = 0

        for original_index, item in indexed:
            size = len(json.dumps(item.content, ensure_ascii=False, default=str))
            exceeds_items = len(selected) >= self._policy.max_items
            exceeds_chars = used_chars + size > self._policy.max_context_chars
            if (exceeds_items or exceeds_chars) and not item.required:
                dropped.append(item.key)
                continue
            selected.append((original_index, item))
            used_chars += size

        selected.sort(key=lambda pair: pair[0])
        return [item for _, item in selected], dropped


__all__ = [
    "ApplicationContextContributor",
    "AttachmentContextContributor",
    "CognitiveContextBuilder",
    "CognitiveContextPolicy",
    "ContextContributor",
]
