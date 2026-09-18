from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from agent_platform.application.cache import CacheService, stable_cache_key
from agent_platform.application.embeddings import EmbeddingProvider, EmbeddingRequest
from agent_platform.application.ontology import OntologyService
from agent_platform.domain.retrieval import RetrievalHit, RetrievalMode, RetrievalQuery, RetrievalResult


class KnowledgeRetrievalError(RuntimeError): pass


@dataclass(frozen=True)
class RetrievalCandidate:
    chunk_id: UUID
    document_id: UUID
    knowledge_base_key: str
    title: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
    source_uri: str | None = None


class KnowledgeSearchBackend(Protocol):
    async def vector_search(self, *, query_vector: list[float], embedding_model: str, query: RetrievalQuery, limit: int) -> list[RetrievalCandidate]: ...
    async def keyword_search(self, *, query: RetrievalQuery, limit: int) -> list[RetrievalCandidate]: ...
    async def ontology_search(self, *, concept_weights: dict[str,float], query: RetrievalQuery, limit: int) -> list[RetrievalCandidate]: ...
    async def parent_for(self, candidate: RetrievalCandidate) -> RetrievalCandidate | None: ...


class KnowledgeRetrievalService:
    def __init__(self,backend:KnowledgeSearchBackend,embedding_provider:EmbeddingProvider,cache:CacheService|None=None,ontology_service:OntologyService|None=None,*,cache_ttl_seconds:int=900)->None:
        self._backend=backend;self._embedding_provider=embedding_provider;self._cache=cache;self._ontology_service=ontology_service;self._cache_ttl_seconds=cache_ttl_seconds

    async def retrieve(self,query:RetrievalQuery)->RetrievalResult:
        cache_key=stable_cache_key(query.model_dump(mode="json"))
        if self._cache is not None:
            cached=await self._cache.get_json("retrieval",cache_key)
            if cached is not None:
                result=RetrievalResult.model_validate(cached);return result.model_copy(update={"metadata":{**result.metadata,"cache":"hit"}})

        candidate_k=max(query.top_k,query.candidate_k);embedding_model=None
        vector_candidates=[];keyword_candidates=[];graph_candidates=[]
        ontology_context=None

        if query.mode in {RetrievalMode.VECTOR,RetrievalMode.HYBRID}:
            embedded=await self._embedding_provider.embed(EmbeddingRequest(texts=[query.text]))
            if len(embedded.vectors)!=1:raise KnowledgeRetrievalError("Embedding provider returned an unexpected vector count for retrieval")
            embedding_model=embedded.model
            vector_candidates=await self._backend.vector_search(query_vector=embedded.vectors[0],embedding_model=embedded.model,query=query,limit=candidate_k)

        if query.mode in {RetrievalMode.KEYWORD,RetrievalMode.HYBRID}:
            keyword_candidates=await self._backend.keyword_search(query=query,limit=candidate_k)

        if query.ontology_enabled and self._ontology_service is not None and query.mode in {RetrievalMode.GRAPH,RetrievalMode.HYBRID}:
            ontology_context=await self._ontology_service.resolve_query(query.text,max_hops=query.ontology_max_hops,max_concepts=query.ontology_max_concepts)
            if ontology_context.concept_weights:
                graph_candidates=await self._backend.ontology_search(concept_weights=ontology_context.concept_weights,query=query,limit=candidate_k)

        if query.mode is RetrievalMode.VECTOR:
            ranked=[(candidate,candidate.score,RetrievalMode.VECTOR) for candidate in vector_candidates]
        elif query.mode is RetrievalMode.KEYWORD:
            ranked=[(candidate,candidate.score,RetrievalMode.KEYWORD) for candidate in keyword_candidates]
        elif query.mode is RetrievalMode.GRAPH:
            ranked=[(candidate,candidate.score,RetrievalMode.GRAPH) for candidate in graph_candidates]
        else:
            ranked=self._rrf_multi([
                (vector_candidates,query.vector_weight),
                (keyword_candidates,query.keyword_weight),
                (graph_candidates,query.ontology_weight),
            ])

        hits=[]
        for candidate,score,method in ranked[:query.top_k]:
            parent=await self._backend.parent_for(candidate) if query.expand_parents else None
            hits.append(RetrievalHit(chunk_id=candidate.chunk_id,document_id=candidate.document_id,knowledge_base_key=candidate.knowledge_base_key,title=candidate.title,content=candidate.content,score=float(score),retrieval_method=method,metadata=candidate.metadata,source_uri=candidate.source_uri,parent_chunk_id=parent.chunk_id if parent else None,parent_content=parent.content if parent else None,parent_metadata=parent.metadata if parent else None))

        metadata={
            "candidate_k":candidate_k,
            "vector_candidates":len(vector_candidates),
            "keyword_candidates":len(keyword_candidates),
            "graph_candidates":len(graph_candidates),
            "expand_parents":query.expand_parents,
            "fusion":"rrf-v2-graph-aware" if query.mode is RetrievalMode.HYBRID else None,
            "cache":"miss" if self._cache is not None else "disabled",
            "ontology_enabled":query.ontology_enabled and self._ontology_service is not None,
            "ontology_seed_concepts":ontology_context.seed_concepts if ontology_context else [],
            "ontology_expanded_concepts":ontology_context.expanded_concepts if ontology_context else [],
            "ontology_max_hops":query.ontology_max_hops,
        }
        result=RetrievalResult(query=query.text,mode=query.mode,hits=hits,embedding_model=embedding_model,metadata=metadata)
        if self._cache is not None:
            stored=result.model_copy(update={"metadata":{**result.metadata,"cache":"stored"}});await self._cache.set_json("retrieval",cache_key,stored.model_dump(mode="json"),ttl_seconds=self._cache_ttl_seconds)
        return result

    @staticmethod
    def _rrf_multi(candidate_sets:list[tuple[list[RetrievalCandidate],float]],*,rrf_k:int=60)->list[tuple[RetrievalCandidate,float,RetrievalMode]]:
        candidates={};scores={};methods={}
        for items,weight in candidate_sets:
            for rank,candidate in enumerate(items,start=1):
                candidates.setdefault(candidate.chunk_id,candidate)
                scores[candidate.chunk_id]=scores.get(candidate.chunk_id,0.0)+weight/(rrf_k+rank)
                method_set=methods.setdefault(candidate.chunk_id,set())
                if candidate.metadata.get("graph_match"):method_set.add(RetrievalMode.GRAPH)
        ordered=sorted(scores,key=lambda chunk_id:(-scores[chunk_id],str(chunk_id)))
        return [(candidates[chunk_id],scores[chunk_id],RetrievalMode.HYBRID) for chunk_id in ordered]

    @staticmethod
    def _rrf(vector_candidates:list[RetrievalCandidate],keyword_candidates:list[RetrievalCandidate],*,vector_weight:float,keyword_weight:float,rrf_k:int=60):
        return KnowledgeRetrievalService._rrf_multi([(vector_candidates,vector_weight),(keyword_candidates,keyword_weight)],rrf_k=rrf_k)
