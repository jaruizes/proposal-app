from uuid import uuid4

import pytest

from agent_platform.application.cache import CacheService, InMemoryCacheProvider
from agent_platform.application.embeddings import EmbeddingResult
from agent_platform.application.retrieval import KnowledgeRetrievalService, RetrievalCandidate
from agent_platform.domain import RetrievalMode, RetrievalQuery


class Embeddings:
    provider_key="fake"; model="fake"; dimensions=2
    def __init__(self): self.calls=0
    async def embed(self,request):
        self.calls+=1
        return EmbeddingResult(vectors=[[1.0,0.0]],model=self.model,dimensions=2)


class Backend:
    def __init__(self): self.calls=0
    async def vector_search(self,**kwargs):
        self.calls+=1
        return [RetrievalCandidate(chunk_id=uuid4(),document_id=uuid4(),knowledge_base_key="kb",title="Doc",content="content",score=.9)]
    async def keyword_search(self,**kwargs): return []
    async def parent_for(self,candidate): return None


@pytest.mark.asyncio
async def test_retrieval_cache_skips_backend_and_embedding_on_hit():
    cache=CacheService(InMemoryCacheProvider(),prefix="test"); backend=Backend(); embeddings=Embeddings()
    service=KnowledgeRetrievalService(backend,embeddings,cache,cache_ttl_seconds=60)
    query=RetrievalQuery(text="hello",mode=RetrievalMode.VECTOR)
    first=await service.retrieve(query); second=await service.retrieve(query)
    assert first.metadata["cache"]=="miss"
    assert second.metadata["cache"]=="hit"
    assert backend.calls==1
    assert embeddings.calls==1
