from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from agent_platform.application.embeddings import EmbeddingProvider, EmbeddingRequest
from agent_platform.domain.retrieval import RetrievalHit, RetrievalMode, RetrievalQuery, RetrievalResult


class KnowledgeRetrievalError(RuntimeError):
    pass


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
    async def vector_search(
        self,
        *,
        query_vector: list[float],
        embedding_model: str,
        query: RetrievalQuery,
        limit: int,
    ) -> list[RetrievalCandidate]: ...

    async def keyword_search(self, *, query: RetrievalQuery, limit: int) -> list[RetrievalCandidate]: ...

    async def parent_for(self, candidate: RetrievalCandidate) -> RetrievalCandidate | None: ...


class KnowledgeRetrievalService:
    def __init__(self, backend: KnowledgeSearchBackend, embedding_provider: EmbeddingProvider) -> None:
        self._backend = backend
        self._embedding_provider = embedding_provider

    async def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        candidate_k = max(query.top_k, query.candidate_k)
        embedding_model: str | None = None
        vector_candidates: list[RetrievalCandidate] = []
        keyword_candidates: list[RetrievalCandidate] = []

        if query.mode in {RetrievalMode.VECTOR, RetrievalMode.HYBRID}:
            embedded = await self._embedding_provider.embed(EmbeddingRequest(texts=[query.text]))
            if len(embedded.vectors) != 1:
                raise KnowledgeRetrievalError("Embedding provider returned an unexpected vector count for retrieval")
            embedding_model = embedded.model
            vector_candidates = await self._backend.vector_search(
                query_vector=embedded.vectors[0],
                embedding_model=embedded.model,
                query=query,
                limit=candidate_k,
            )

        if query.mode in {RetrievalMode.KEYWORD, RetrievalMode.HYBRID}:
            keyword_candidates = await self._backend.keyword_search(query=query, limit=candidate_k)

        if query.mode is RetrievalMode.VECTOR:
            ranked = [(candidate, candidate.score, RetrievalMode.VECTOR) for candidate in vector_candidates]
        elif query.mode is RetrievalMode.KEYWORD:
            ranked = [(candidate, candidate.score, RetrievalMode.KEYWORD) for candidate in keyword_candidates]
        else:
            ranked = self._rrf(
                vector_candidates,
                keyword_candidates,
                vector_weight=query.vector_weight,
                keyword_weight=query.keyword_weight,
            )

        hits: list[RetrievalHit] = []
        for candidate, score, method in ranked[: query.top_k]:
            parent = await self._backend.parent_for(candidate) if query.expand_parents else None
            hits.append(
                RetrievalHit(
                    chunk_id=candidate.chunk_id,
                    document_id=candidate.document_id,
                    knowledge_base_key=candidate.knowledge_base_key,
                    title=candidate.title,
                    content=candidate.content,
                    score=float(score),
                    retrieval_method=method,
                    metadata=candidate.metadata,
                    source_uri=candidate.source_uri,
                    parent_chunk_id=parent.chunk_id if parent else None,
                    parent_content=parent.content if parent else None,
                    parent_metadata=parent.metadata if parent else None,
                )
            )

        return RetrievalResult(
            query=query.text,
            mode=query.mode,
            hits=hits,
            embedding_model=embedding_model,
            metadata={
                "candidate_k": candidate_k,
                "vector_candidates": len(vector_candidates),
                "keyword_candidates": len(keyword_candidates),
                "expand_parents": query.expand_parents,
                "fusion": "rrf-v1" if query.mode is RetrievalMode.HYBRID else None,
            },
        )

    @staticmethod
    def _rrf(
        vector_candidates: list[RetrievalCandidate],
        keyword_candidates: list[RetrievalCandidate],
        *,
        vector_weight: float,
        keyword_weight: float,
        rrf_k: int = 60,
    ) -> list[tuple[RetrievalCandidate, float, RetrievalMode]]:
        candidates: dict[UUID, RetrievalCandidate] = {}
        scores: dict[UUID, float] = {}
        for rank, candidate in enumerate(vector_candidates, start=1):
            candidates[candidate.chunk_id] = candidate
            scores[candidate.chunk_id] = scores.get(candidate.chunk_id, 0.0) + vector_weight / (rrf_k + rank)
        for rank, candidate in enumerate(keyword_candidates, start=1):
            candidates.setdefault(candidate.chunk_id, candidate)
            scores[candidate.chunk_id] = scores.get(candidate.chunk_id, 0.0) + keyword_weight / (rrf_k + rank)
        ordered = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], str(chunk_id)))
        return [(candidates[chunk_id], scores[chunk_id], RetrievalMode.HYBRID) for chunk_id in ordered]
