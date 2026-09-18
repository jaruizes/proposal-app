from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from agent_platform.application.cache import CacheService
from agent_platform.application.repositories import KnowledgeRepository
from agent_platform.domain.ontology import OntologyConcept, OntologyMapping, OntologyRelationship, OntologyTargetType


class OntologyError(RuntimeError): pass
class OntologyNotFoundError(OntologyError): pass
class OntologyConflictError(OntologyError): pass


@dataclass(frozen=True)
class OntologyQueryContext:
    seed_concepts: list[str]
    concept_weights: dict[str, float]
    max_hops: int

    @property
    def expanded_concepts(self) -> list[str]:
        return [key for key in self.concept_weights if key not in set(self.seed_concepts)]


class OntologyRepository(Protocol):
    async def list_concepts(self, concept_type: str | None = None) -> list[OntologyConcept]: ...
    async def get_concept(self, key: str) -> OntologyConcept | None: ...
    async def create_concept(self, item: OntologyConcept) -> OntologyConcept: ...
    async def update_concept(self, item: OntologyConcept) -> OntologyConcept: ...
    async def delete_concept(self, key: str) -> None: ...
    async def list_relationships(self, concept_key: str | None = None) -> list[OntologyRelationship]: ...
    async def create_relationship(self, item: OntologyRelationship) -> OntologyRelationship: ...
    async def delete_relationship(self, relationship_id: UUID) -> None: ...
    async def replace_mappings(self, target_type: OntologyTargetType, target_id: UUID, mappings: list[OntologyMapping]) -> list[OntologyMapping]: ...
    async def list_mappings(self, target_type: OntologyTargetType | None = None, target_id: UUID | None = None) -> list[OntologyMapping]: ...


class OntologyService:
    def __init__(self, repository: OntologyRepository, knowledge: KnowledgeRepository, cache: CacheService | None = None) -> None:
        self._repository=repository; self._knowledge=knowledge; self._cache=cache

    async def _invalidate(self) -> None:
        if self._cache is None: return
        for namespace in ("ontology","retrieval","cognitive-rag"):
            await self._cache.invalidate_namespace(namespace)

    async def list_concepts(self, concept_type: str | None = None): return await self._repository.list_concepts(concept_type)
    async def get_concept(self,key:str):
        item=await self._repository.get_concept(key)
        if item is None: raise OntologyNotFoundError(f"Ontology concept '{key}' not found")
        return item

    async def create_concept(self,item:OntologyConcept):
        if await self._repository.get_concept(item.key): raise OntologyConflictError(f"Ontology concept '{item.key}' already exists")
        created=await self._repository.create_concept(item); await self._invalidate(); return created

    async def update_concept(self,key:str,item:OntologyConcept):
        if key != item.key: raise OntologyConflictError("Concept key cannot be changed")
        await self.get_concept(key); updated=await self._repository.update_concept(item); await self._invalidate(); return updated

    async def delete_concept(self,key:str):
        await self.get_concept(key); await self._repository.delete_concept(key); await self._invalidate()

    async def list_relationships(self,concept_key:str|None=None): return await self._repository.list_relationships(concept_key)

    async def create_relationship(self,item:OntologyRelationship):
        if item.source_key==item.target_key: raise OntologyConflictError("Self relationships are not allowed")
        await self.get_concept(item.source_key); await self.get_concept(item.target_key)
        created=await self._repository.create_relationship(item); await self._invalidate(); return created

    async def delete_relationship(self,relationship_id:UUID):
        await self._repository.delete_relationship(relationship_id); await self._invalidate()

    async def list_mappings(self,target_type:OntologyTargetType|None=None,target_id:UUID|None=None):
        return await self._repository.list_mappings(target_type,target_id)

    async def match_concepts(self, content: str, *, max_concepts: int = 50) -> list[OntologyConcept]:
        normalized=content.casefold()
        matches=[]
        for concept in await self._repository.list_concepts():
            if not concept.enabled: continue
            terms=[concept.name,*concept.aliases,concept.key.split(".")[-1].replace("-"," ")]
            if any(re.search(r"(?<!\w)"+re.escape(term.strip().casefold())+r"(?!\w)",normalized) for term in terms if term and term.strip()):
                matches.append(concept)
            if len(matches)>=max_concepts: break
        return matches

    async def resolve_query(self, text: str, *, max_hops: int = 1, max_concepts: int = 12) -> OntologyQueryContext:
        seeds=await self.match_concepts(text,max_concepts=max_concepts)
        seed_keys=[concept.key for concept in seeds]
        weights={key:1.0 for key in seed_keys}
        frontier=list(seed_keys)
        for depth in range(1,max_hops+1):
            if not frontier or len(weights)>=max_concepts: break
            next_frontier=[]
            for key in frontier:
                for relationship in await self._repository.list_relationships(key):
                    neighbor=relationship.target_key if relationship.source_key==key else relationship.source_key
                    if neighbor in weights: continue
                    weights[neighbor]=max(0.35,1.0-(0.3*depth))
                    next_frontier.append(neighbor)
                    if len(weights)>=max_concepts: break
                if len(weights)>=max_concepts: break
            frontier=next_frontier
        return OntologyQueryContext(seed_concepts=seed_keys,concept_weights=weights,max_hops=max_hops)

    async def tag_text(self,*,target_type:OntologyTargetType,target_id:UUID,content:str)->list[OntologyMapping]:
        concepts=await self.match_concepts(content)
        normalized=content.casefold()
        mappings=[]
        for concept in concepts:
            terms=[concept.name,*concept.aliases,concept.key.split(".")[-1].replace("-"," ")]
            matched=next((term for term in sorted({t.strip() for t in terms if t and t.strip()},key=len,reverse=True) if re.search(r"(?<!\w)"+re.escape(term.casefold())+r"(?!\w)",normalized)),concept.name)
            mappings.append(OntologyMapping(target_type=target_type,target_id=target_id,concept_key=concept.key,confidence=1.0,source="deterministic",metadata={"matched_term":matched}))
        result=await self._repository.replace_mappings(target_type,target_id,mappings)
        await self._invalidate()
        return result

    async def tag_document(self,document_id:UUID)->list[OntologyMapping]:
        document=await self._knowledge.get_document(document_id)
        if document is None: raise OntologyNotFoundError(f"Knowledge document '{document_id}' not found")
        all_mappings=await self.tag_text(target_type=OntologyTargetType.DOCUMENT,target_id=document.id,content=document.content)
        for chunk in await self._knowledge.list_chunks(document.id):
            all_mappings.extend(await self.tag_text(target_type=OntologyTargetType.CHUNK,target_id=chunk.id,content=chunk.content))
        return all_mappings
