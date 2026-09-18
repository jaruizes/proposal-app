from __future__ import annotations

import asyncio
import json
from typing import Protocol

from agent_platform.application.cache import CacheService, stable_cache_key
from agent_platform.application.memory import MemoryService
from agent_platform.application.retrieval import KnowledgeRetrievalService
from agent_platform.domain import AgentDefinition, AgentExecutionRequest, CognitiveContext, CognitiveContextItem, CognitiveSection, EpistemicLabel, MemoryKind, MemoryRecall, MemoryScope, MemoryScopeType, RetrievalFilters, RetrievalMode, RetrievalQuery, SkillDefinition


class ContextContributor(Protocol):
    name: str
    required: bool
    async def contribute(self, agent: AgentDefinition, skill: SkillDefinition | None, request: AgentExecutionRequest) -> list[CognitiveContextItem]: ...


class ApplicationContextContributor:
    name = "application-context"
    required = True
    async def contribute(self, agent, skill, request):
        if not request.context: return []
        return [CognitiveContextItem(key="application-context", section=CognitiveSection.BUSINESS_CONTEXT, content=request.context, source=self.name, priority=100, required=True)]


class AttachmentContextContributor:
    name = "attachments"
    required = True
    async def contribute(self, agent, skill, request):
        return [CognitiveContextItem(key=f"attachment:{index}:{attachment.name}", section=CognitiveSection.SOURCE_MATERIAL, content={"name": attachment.name, "media_type": attachment.media_type, "uri": attachment.uri, "content": attachment.content}, source=self.name, priority=95, required=True, metadata=attachment.metadata) for index, attachment in enumerate(request.attachments)]


class MemoryContextContributor:
    name = "memory"
    required = False

    def __init__(self, service: MemoryService) -> None:
        self._service = service

    async def contribute(self, agent, skill, request):
        config = skill.constraints.get("memory", {}) if skill and isinstance(skill.constraints, dict) else {}
        if config.get("enabled", True) is False: return []
        scopes: list[MemoryScope] = []
        if request.correlation_id is not None: scopes.append(MemoryScope(type=MemoryScopeType.CORRELATION, key=str(request.correlation_id)))
        if bool(config.get("include_agent_scope", False)): scopes.append(MemoryScope(type=MemoryScopeType.AGENT, key=agent.key))
        if bool(config.get("include_global", False)): scopes.append(MemoryScope(type=MemoryScopeType.GLOBAL, key="*"))
        for custom in config.get("custom_scopes", []) or []:
            if isinstance(custom, str) and custom.strip(): scopes.append(MemoryScope(type=MemoryScopeType.CUSTOM, key=custom.strip()))
        if not scopes: return []
        kinds = [MemoryKind(value) for value in config.get("kinds", []) or []]
        entries = await self._service.recall(MemoryRecall(
            scopes=scopes,
            kinds=kinds,
            agent_key=agent.key if bool(config.get("same_agent_only", False)) else None,
            skill_key=skill.key if skill and bool(config.get("same_skill_only", False)) else None,
            min_importance=float(config.get("min_importance", 0.0)),
            limit=int(config.get("max_items", 6)),
        ))
        label_by_kind = {MemoryKind.FACT: EpistemicLabel.FACT, MemoryKind.DECISION: EpistemicLabel.DECISION}
        return [CognitiveContextItem(key=f"memory:{entry.id}", section=CognitiveSection.MEMORY, content={"kind": entry.kind.value, "content": entry.content}, label=label_by_kind.get(entry.kind, EpistemicLabel.UNCLASSIFIED), source=f"memory://{entry.id}", priority=max(70, 86-rank), required=False, metadata={"memory_id": str(entry.id), "scope_type": entry.scope_type.value, "scope_key": entry.scope_key, "importance": entry.importance, **entry.metadata}) for rank, entry in enumerate(entries, start=1)]


class KnowledgeRetrievalContributor:
    name = "knowledge-retrieval"
    required = False

    def __init__(self, service: KnowledgeRetrievalService, cache: CacheService | None = None, *, cache_ttl_seconds: int = 900) -> None:
        self._service = service
        self._cache = cache
        self._cache_ttl_seconds = cache_ttl_seconds

    async def contribute(self, agent, skill, request):
        if skill is None or not skill.knowledge_sources: return []
        config = skill.constraints.get("retrieval", {}) if isinstance(skill.constraints, dict) else {}
        cache_key = stable_cache_key({
            "agent": [agent.key, agent.version],
            "skill": [skill.key, skill.version],
            "objective": request.objective,
            "knowledge_sources": skill.knowledge_sources,
            "retrieval": config,
        })
        if self._cache is not None:
            cached = await self._cache.get_json("cognitive-rag", cache_key)
            if cached is not None:
                return [CognitiveContextItem.model_validate(item).model_copy(update={"metadata": {**item.get("metadata", {}), "cognitive_cache": "hit"}}) for item in cached]

        mode = RetrievalMode(str(config.get("mode", RetrievalMode.HYBRID.value)))
        top_k = int(config.get("top_k", 5)); candidate_k = int(config.get("candidate_k", max(20, top_k)))
        result = await self._service.retrieve(RetrievalQuery(text=self._query_text(skill, request), mode=mode, top_k=top_k, candidate_k=candidate_k, filters=RetrievalFilters(knowledge_base_keys=list(skill.knowledge_sources)), expand_parents=bool(config.get("expand_parents", True)), vector_weight=float(config.get("vector_weight", 1.0)), keyword_weight=float(config.get("keyword_weight", 1.0))))
        items=[]
        for rank, hit in enumerate(result.hits, start=1):
            source=hit.source_uri or f"knowledge://{hit.knowledge_base_key}/{hit.document_id}"
            items.append(CognitiveContextItem(key=f"knowledge:{hit.chunk_id}", section=CognitiveSection.RETRIEVED_KNOWLEDGE, content={"title": hit.title, "excerpt": hit.content, "parent_context": hit.parent_content, "source_uri": hit.source_uri}, label=EpistemicLabel.REFERENCE, source=source, priority=max(55,76-rank), required=False, metadata={"rank":rank,"score":hit.score,"retrieval_method":hit.retrieval_method.value,"retrieval_query":result.query,"knowledge_base_key":hit.knowledge_base_key,"document_id":str(hit.document_id),"chunk_id":str(hit.chunk_id),"chunk_metadata":hit.metadata,"parent_chunk_id":str(hit.parent_chunk_id) if hit.parent_chunk_id else None,"parent_metadata":hit.parent_metadata,"embedding_model":result.embedding_model,"cognitive_cache":"miss" if self._cache is not None else "disabled"}))
        if self._cache is not None:
            await self._cache.set_json("cognitive-rag", cache_key, [item.model_dump(mode="json") for item in items], ttl_seconds=self._cache_ttl_seconds)
        return items

    @staticmethod
    def _query_text(skill, request):
        task=request.objective.strip(); objective=skill.objective.strip()
        return task if not objective or objective.lower()==task.lower() else f"{objective}\n\nCurrent task: {task}"


class CognitiveContextPolicy:
    def __init__(self, *, max_items: int = 50, max_context_chars: int = 80_000) -> None:
        self.max_items=max_items; self.max_context_chars=max_context_chars


class CognitiveContextBuilder:
    def __init__(self, contributors: list[ContextContributor] | None = None, policy: CognitiveContextPolicy | None = None) -> None:
        self._contributors = contributors if contributors is not None else [ApplicationContextContributor(), AttachmentContextContributor()]
        self._policy = policy or CognitiveContextPolicy()

    async def build(self, agent, skill, request):
        async def run(contributor):
            try: return await contributor.contribute(agent, skill, request), None
            except Exception as exc:
                if contributor.required: raise
                return [], f"{contributor.name}: {str(exc) or type(exc).__name__}"
        results=await asyncio.gather(*(run(c) for c in self._contributors)); groups=[items for items,_ in results]; warnings=[w for _,w in results if w]
        candidates=[item for group in groups for item in group]; selected,dropped=self._apply_budget(candidates)
        skill_tools=skill.allowed_tools if skill else []
        if skill_tools and agent.allowed_tools: allowed=[tool for tool in skill_tools if tool in set(agent.allowed_tools)]
        elif skill_tools: allowed=list(skill_tools)
        else: allowed=list(agent.allowed_tools)
        return CognitiveContext(items=selected, knowledge_sources=list(skill.knowledge_sources if skill else []), knowledge_scopes=list(agent.knowledge_scopes), allowed_tools=allowed, warnings=warnings, dropped_items=dropped, metadata={"agent_key":agent.key,"agent_version":agent.version,"skill_key":skill.key if skill else None,"skill_version":skill.version if skill else None,"contributors":[c.name for c in self._contributors],"budget":{"max_items":self._policy.max_items,"max_context_chars":self._policy.max_context_chars}})

    def _apply_budget(self, items):
        indexed=list(enumerate(items)); indexed.sort(key=lambda pair:(-pair[1].priority,pair[0])); selected=[]; dropped=[]; used=0
        for original,item in indexed:
            size=len(json.dumps(item.content,ensure_ascii=False,default=str)); exceeds=len(selected)>=self._policy.max_items or used+size>self._policy.max_context_chars
            if exceeds and not item.required: dropped.append(item.key); continue
            selected.append((original,item)); used+=size
        selected.sort(key=lambda pair:pair[0]); return [item for _,item in selected],dropped


__all__=["ApplicationContextContributor","AttachmentContextContributor","MemoryContextContributor","KnowledgeRetrievalContributor","CognitiveContextBuilder","CognitiveContextPolicy","ContextContributor"]
