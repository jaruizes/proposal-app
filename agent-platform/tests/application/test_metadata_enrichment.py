import pytest

from agent_platform.application.ingestion import KnowledgeIngestionService
from agent_platform.application.metadata_enrichment import DeterministicMetadataEnricher, MetadataEnrichmentProfile
from agent_platform.domain import KnowledgeChunk, KnowledgeDocument, KnowledgeDocumentStatus
from agent_platform.providers.embeddings import HashEmbeddingProvider


class Repo:
    def __init__(self, document):
        self.document = document
        self.chunks = []

    async def get_document(self, document_id):
        return self.document if self.document.id == document_id else None

    async def update_document(self, item):
        self.document = item
        return item

    async def replace_chunks(self, document_id, chunks):
        self.chunks = list(chunks)
        return chunks

    async def list_chunks(self, document_id):
        return list(self.chunks)


@pytest.mark.asyncio
async def test_standard_metadata_enrichment_is_deterministic_and_preserves_user_metadata():
    document = KnowledgeDocument(
        knowledge_base_key="architecture-references",
        title="OpenShift reference",
        content="# Platform Architecture\n\nThe platform uses OpenShift and GitOps with Argo CD. The architecture uses OpenShift for workloads.",
        media_type="text/markdown",
        metadata={"sector": "banking"},
    )
    repo = Repo(document)
    service = KnowledgeIngestionService(repo, HashEmbeddingProvider(dimensions=384))

    result = await service.ingest(document.id, chunk_size=80, overlap=10, metadata_enrichment="standard")

    assert result.status is KnowledgeDocumentStatus.READY
    assert result.metadata_enrichment is MetadataEnrichmentProfile.STANDARD
    assert repo.document.metadata["sector"] == "banking"
    enrichment = repo.document.metadata["enrichment"]
    assert enrichment["profile"] == "standard"
    assert enrichment["language"] == "en"
    assert enrichment["content_hash"]
    assert enrichment["keywords"]
    assert enrichment["headings"][0]["text"] == "Platform Architecture"
    assert repo.chunks[0].metadata["enrichment"]["content_hash"]
    assert "document_keywords" in repo.chunks[0].metadata["enrichment"]


@pytest.mark.asyncio
async def test_basic_profile_skips_keywords_and_headings():
    enricher = DeterministicMetadataEnricher()
    document = KnowledgeDocument(
        knowledge_base_key="reference-offers",
        title="Oferta",
        content="La plataforma utiliza arquitectura de eventos para integrar los sistemas.",
    )

    metadata = await enricher.enrich_document(
        document,
        document.content,
        profile=MetadataEnrichmentProfile.BASIC,
        max_keywords=8,
    )

    assert metadata["profile"] == "basic"
    assert metadata["language"] == "es"
    assert "keywords" not in metadata
    assert "headings" not in metadata


@pytest.mark.asyncio
async def test_none_profile_removes_existing_enrichment_without_touching_other_metadata():
    document = KnowledgeDocument(
        knowledge_base_key="case-studies",
        title="Case",
        content="Some reusable reference content.",
        metadata={"owner": "architecture", "enrichment": {"old": True}},
    )
    repo = Repo(document)
    repo.chunks = [
        KnowledgeChunk(
            document_id=document.id,
            ordinal=0,
            content=document.content,
            metadata={"custom": "keep", "enrichment": {"old": True}},
        )
    ]
    service = KnowledgeIngestionService(repo, HashEmbeddingProvider(dimensions=384))

    result = await service.enrich_existing(document.id, metadata_enrichment="none")

    assert result.profile is MetadataEnrichmentProfile.NONE
    assert result.chunks_enriched == 1
    assert repo.document.metadata == {"owner": "architecture"}
    assert repo.chunks[0].metadata == {"custom": "keep"}


@pytest.mark.asyncio
async def test_existing_chunks_can_be_reenriched_without_reembedding():
    document = KnowledgeDocument(
        knowledge_base_key="case-studies",
        title="Case",
        content="The project used Kubernetes, GitOps and observability for the platform.",
        metadata={"owner": "delivery"},
        status=KnowledgeDocumentStatus.READY,
    )
    repo = Repo(document)
    original_embedding = [0.1, 0.2, 0.3]
    repo.chunks = [
        KnowledgeChunk(
            document_id=document.id,
            ordinal=0,
            content=document.content,
            embedding=original_embedding,
            embedding_model="test-model",
        )
    ]
    service = KnowledgeIngestionService(repo, HashEmbeddingProvider(dimensions=384))

    result = await service.enrich_existing(document.id, metadata_enrichment="standard", max_keywords=4)

    assert result.chunks_enriched == 1
    assert repo.chunks[0].embedding == original_embedding
    assert repo.chunks[0].embedding_model == "test-model"
    assert len(repo.chunks[0].metadata["enrichment"]["keywords"]) <= 4
