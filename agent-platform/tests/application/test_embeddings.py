import pytest
from agent_platform.application.embeddings import EmbeddingRequest
from agent_platform.providers.embeddings import HashEmbeddingProvider

@pytest.mark.asyncio
async def test_hash_embeddings_are_deterministic_and_normalized():
    provider=HashEmbeddingProvider(dimensions=32)
    first=await provider.embed(EmbeddingRequest(texts=["OpenShift Kafka observability"]))
    second=await provider.embed(EmbeddingRequest(texts=["OpenShift Kafka observability"]))
    assert first.vectors==second.vectors
    assert first.dimensions==32
    assert len(first.vectors[0])==32
    norm=sum(v*v for v in first.vectors[0])**0.5
    assert norm==pytest.approx(1.0)
