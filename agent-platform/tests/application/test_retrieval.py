from uuid import UUID, uuid4

import pytest

from agent_platform.application.embeddings import EmbeddingResult
from agent_platform.application.retrieval import KnowledgeRetrievalService, RetrievalCandidate
from agent_platform.domain.retrieval import RetrievalMode, RetrievalQuery


class FakeEmbeddingProvider:
    provider_key = "fake"
    model = "fake-embedding-v1"
    dimensions = 3

    def __init__(self) -> None:
        self.calls = 0

    async def embed(self, request):
        self.calls += 1
        return EmbeddingResult(vectors=[[0.1, 0.2, 0.3] for _ in request.texts], model=self.model, dimensions=3)


class FakeBackend:
    def __init__(self, vector=None, keyword=None, parents=None):
        self.vector = vector or []
        self.keyword = keyword or []
        self.parents = parents or {}

    async def vector_search(self, **kwargs):
        return self.vector[: kwargs["limit"]]

    async def keyword_search(self, **kwargs):
        return self.keyword[: kwargs["limit"]]

    async def ontology_search(self, **kwargs):
        return []

    async def parent_for(self, candidate):
        return self.parents.get(candidate.chunk_id)


def candidate(*, score: float, content: str, metadata=None, chunk_id=None):
    return RetrievalCandidate(
        chunk_id=chunk_id or uuid4(),
        document_id=uuid4(),
        knowledge_base_key="architecture-references",
        title="Architecture",
        content=content,
        score=score,
        metadata=metadata or {},
        source_uri="upload://architecture.md",
    )


@pytest.mark.asyncio
async def test_keyword_retrieval_does_not_embed_query():
    embedding = FakeEmbeddingProvider()
    hit = candidate(score=0.8, content="OpenShift GitOps")
    service = KnowledgeRetrievalService(FakeBackend(keyword=[hit]), embedding)

    result = await service.retrieve(RetrievalQuery(text="OpenShift", mode=RetrievalMode.KEYWORD))

    assert embedding.calls == 0
    assert result.hits[0].chunk_id == hit.chunk_id
    assert result.hits[0].retrieval_method is RetrievalMode.KEYWORD


@pytest.mark.asyncio
async def test_vector_retrieval_embeds_query_once():
    embedding = FakeEmbeddingProvider()
    hit = candidate(score=0.91, content="Event driven architecture")
    service = KnowledgeRetrievalService(FakeBackend(vector=[hit]), embedding)

    result = await service.retrieve(RetrievalQuery(text="event architecture", mode=RetrievalMode.VECTOR))

    assert embedding.calls == 1
    assert result.embedding_model == "fake-embedding-v1"
    assert result.hits[0].score == pytest.approx(0.91)


@pytest.mark.asyncio
async def test_hybrid_uses_weighted_rrf_and_deduplicates_chunks():
    shared = uuid4()
    a = candidate(score=0.9, content="A", chunk_id=shared)
    b = candidate(score=0.8, content="B")
    service = KnowledgeRetrievalService(
        FakeBackend(vector=[a, b], keyword=[b, a]),
        FakeEmbeddingProvider(),
    )

    result = await service.retrieve(
        RetrievalQuery(text="architecture", mode=RetrievalMode.HYBRID, vector_weight=2.0, keyword_weight=1.0)
    )

    assert len(result.hits) == 2
    assert result.hits[0].chunk_id == a.chunk_id
    assert result.hits[0].retrieval_method is RetrievalMode.HYBRID
    assert result.metadata["fusion"] == "rrf-v2-graph-aware"


@pytest.mark.asyncio
async def test_hierarchical_child_can_expand_parent_context():
    child = candidate(score=0.95, content="child", metadata={"hierarchy_level": "child", "parent_index": 0})
    parent = candidate(score=0.0, content="full parent context", metadata={"hierarchy_level": "parent", "parent_index": 0})
    service = KnowledgeRetrievalService(FakeBackend(keyword=[child], parents={child.chunk_id: parent}), FakeEmbeddingProvider())

    result = await service.retrieve(RetrievalQuery(text="context", mode=RetrievalMode.KEYWORD, expand_parents=True))

    assert result.hits[0].parent_chunk_id == parent.chunk_id
    assert result.hits[0].parent_content == "full parent context"
