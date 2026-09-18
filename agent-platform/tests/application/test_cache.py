import asyncio

import pytest

from agent_platform.application.cache import CacheService, CachedEmbeddingProvider, InMemoryCacheProvider
from agent_platform.application.embeddings import EmbeddingRequest, EmbeddingResult


class FakeEmbeddingProvider:
    provider_key="fake"
    model="fake-v1"
    dimensions=2
    def __init__(self): self.calls=[]
    async def embed(self,request):
        self.calls.append(list(request.texts))
        return EmbeddingResult(vectors=[[float(len(text)),1.0] for text in request.texts],model=self.model,dimensions=self.dimensions)


@pytest.mark.asyncio
async def test_cache_service_ttl_and_invalidation():
    cache=CacheService(InMemoryCacheProvider(),prefix="test")
    await cache.set_json("rag","a",{"value":1},ttl_seconds=1)
    assert await cache.get_json("rag","a")=={"value":1}
    assert await cache.invalidate_namespace("rag")==1
    assert await cache.get_json("rag","a") is None
    stats=cache.stats()["rag"]
    assert stats["hits"]==1
    assert stats["misses"]==1
    assert stats["invalidations"]==1


@pytest.mark.asyncio
async def test_cached_embedding_provider_only_generates_misses():
    cache=CacheService(InMemoryCacheProvider(),prefix="test")
    delegate=FakeEmbeddingProvider(); provider=CachedEmbeddingProvider(delegate,cache,ttl_seconds=60)
    first=await provider.embed(EmbeddingRequest(texts=["alpha","beta"]))
    second=await provider.embed(EmbeddingRequest(texts=["alpha","beta"]))
    assert first.vectors==second.vectors
    assert delegate.calls==[["alpha","beta"]]
    assert cache.stats()["embedding"]["hits"]==2
    assert cache.stats()["embedding"]["misses"]==2
