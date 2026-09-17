import pytest

from agent_platform.application.chunking import ChunkingStrategyName
from agent_platform.application.ingestion import KnowledgeIngestionService, TextChunker, TextNormalizer
from agent_platform.domain import KnowledgeDocument, KnowledgeDocumentStatus
from agent_platform.providers.embeddings import HashEmbeddingProvider


class Repo:
    def __init__(self, document): self.document = document; self.chunks = []
    async def get_document(self, document_id): return self.document if self.document.id == document_id else None
    async def update_document(self, item): self.document = item; return item
    async def replace_chunks(self, document_id, chunks): self.chunks = list(chunks); return chunks


def test_normalizer_and_chunker_are_deterministic():
    text = "\ufeff# Title\r\n\r\nParagraph one.\r\n\r\n\r\nParagraph two."
    normalized = TextNormalizer().normalize(text)
    assert normalized == "# Title\n\nParagraph one.\n\nParagraph two."
    chunks = TextChunker(chunk_size=24, overlap=5).split(normalized)
    assert len(chunks) >= 2
    assert all(content for content, _, _ in chunks)


@pytest.mark.asyncio
async def test_ingestion_defaults_to_fixed_and_embeds_all_fixed_chunks():
    document = KnowledgeDocument(knowledge_base_key="architecture-references", title="Test", content="# Heading\n\n" + ("OpenShift platform architecture. " * 30), media_type="text/markdown")
    repo = Repo(document)
    service = KnowledgeIngestionService(repo, HashEmbeddingProvider(dimensions=384))
    result = await service.ingest(document.id, chunk_size=180, overlap=30, embed=True)
    assert result.status is KnowledgeDocumentStatus.READY
    assert result.chunking_strategy is ChunkingStrategyName.FIXED
    assert result.chunks > 1
    assert result.embedded_chunks == result.chunks
    assert result.embedding_model == "hash-embedding-v1"
    assert repo.document.status is KnowledgeDocumentStatus.READY
    assert len(repo.chunks[0].embedding) == 384
    assert repo.chunks[0].metadata["chunking_strategy"] == "fixed-v1"


@pytest.mark.asyncio
async def test_hierarchical_ingestion_embeds_children_but_not_parents():
    document = KnowledgeDocument(knowledge_base_key="reference-offers", title="Offer", content="Architecture section. " * 200, media_type="text/plain")
    repo = Repo(document)
    service = KnowledgeIngestionService(repo, HashEmbeddingProvider(dimensions=384))
    result = await service.ingest(document.id, chunking_strategy="hierarchical", parent_size=800, child_size=220, child_overlap=30)
    parents = [chunk for chunk in repo.chunks if chunk.metadata.get("hierarchy_level") == "parent"]
    children = [chunk for chunk in repo.chunks if chunk.metadata.get("hierarchy_level") == "child"]
    assert parents and children
    assert all(chunk.embedding is None for chunk in parents)
    assert all(len(chunk.embedding) == 384 for chunk in children)
    assert result.embedded_chunks == len(children)
