from __future__ import annotations

import asyncio
import json
from typing import Protocol

from agent_platform.application.retrieval import KnowledgeRetrievalService
from agent_platform.domain import (
    AgentDefinition,
    AgentExecutionRequest,
    CognitiveContext,
    CognitiveContextItem,
    CognitiveSection,
    EpistemicLabel,
    RetrievalFilters,
    RetrievalMode,
    RetrievalQuery,
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


class KnowledgeRetrievalContributor:
    """Retrieves skill-scoped corporate knowledge and labels it as REFERENCE context."""

    name = "knowledge-retrieval"
    required = False

    def __init__(self, service: KnowledgeRetrievalService) -> None:
        self._service = service

    async def contribute(self, agent, skill, request) -> list[CognitiveContextItem]:
        if skill is None or not skill.knowledge_sources:
            return []

        config = skill.constraints.get("retrieval", {}) if isinstance(skill.constraints, dict) else {}
        mode = RetrievalMode(str(config.get("mode", RetrievalMode.HYBRID.value)))
        top_k = int(config.get("top_k", 5))
        candidate_k = int(config.get("candidate_k", max(20, top_k)))
        expand_parents = bool(config.get("expand_parents", True))
        vector_weight = float(config.get("vector_weight", 1.0))
        keyword_weight = float(config.get("keyword_weight", 1.0))

        query_text = self._query_text(skill, request)
        result = await self._service.retrieve(
            RetrievalQuery(
                text=query_text,
                mode=mode,
                top_k=top_k,
                candidate_k=candidate_k,
                filters=RetrievalFilters(knowledge_base_keys=list(skill.knowledge_sources)),
                expand_parents=expand_parents,
                vector_weight=vector_weight,
                keyword_weight=keyword_weight,
            )
        )

        items: list[CognitiveContextItem] = []
        for rank, hit in enumerate(result.hits, start=1):
            source = hit.source_uri or f"knowledge://{hit.knowledge_base_key}/{hit.document_id}"
            content = {
                "title": hit.title,
                "excerpt": hit.content,
                "parent_context": hit.parent_content,
                "source_uri": hit.source_uri,
            }
            metadata = {
                "rank": rank,
                "score": hit.score,
                "retrieval_method": hit.retrieval_method.value,
                "retrieval_query": result.query,
                "knowledge_base_key": hit.knowledge_base_key,
                "document_id": str(hit.document_id),
                "chunk_id": str(hit.chunk_id),
                "chunk_metadata": hit.metadata,
                "parent_chunk_id": str(hit.parent_chunk_id) if hit.parent_chunk_id else None,
                "parent_metadata": hit.parent_metadata,
                "embedding_model": result.embedding_model,
            }
            items.append(
                CognitiveContextItem(
                    key=f"knowledge:{hit.chunk_id}",
                    section=CognitiveSection.RETRIEVED_KNOWLEDGE,
                    content=content,
                    label=EpistemicLabel.REFERENCE,
                    source=source,
                    priority=max(55, 76 - rank),
                    required=False,
                    metadata=metadata,
                )
            )
        return items

    @staticmethod
    def _query_text(skill: SkillDefinition, request: AgentExecutionRequest) -> str:
        task = request.objective.strip()
        skill_objective = skill.objective.strip()
        if not skill_objective or skill_objective.lower() == task.lower():
            return task
        return f"{skill_objective}\n\nCurrent task: {task}"


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
        self._contributors = (
            contributors
            if contributors is not None
            else [ApplicationContextContributor(), AttachmentContextContributor()]
        )
        self._policy = policy or CognitiveContextPolicy()

    async def build(
        self,
        agent: AgentDefinition,
        skill: SkillDefinition | None,
        request: AgentExecutionRequest,
    ) -> CognitiveContext:
        async def run(contributor: ContextContributor):
            try:
                return await contributor.contribute(agent, skill, request), None
            except Exception as exc:
                if contributor.required:
                    raise
                return [], f"{contributor.name}: {str(exc) or type(exc).__name__}"

        results = await asyncio.gather(*(run(contributor) for contributor in self._contributors))
        groups = [items for items, _ in results]
        warnings = [warning for _, warning in results if warning]
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
    "KnowledgeRetrievalContributor",
]
