from uuid import UUID
import pytest
from agent_platform.application.ingestion import KnowledgeIngestionService, TextChunker, TextNormalizer
from agent_platform.domain import KnowledgeDocument, KnowledgeDocumentStatus
from agent_platform.providers.embeddings import HashEmbeddingProvider

class Repo:
    def __init__(self,document): self.document=document; self.chunks=[]
    async def get_document(self,document_id): return self.document if self.document.id==document_id else None
    async def update_document(self,item): self.document=item; return item
    async def replace_chunks(self,document_id,chunks): self.chunks=list(chunks); return chunks


def test_normalizer_and_chunker_are_deterministic():
    text="\ufeff# Title\r\n\r\nParagraph one.\r\n\r\n\r\nParagraph two."
    normalized=TextNormalizer().normalize(text)
    assert normalized=="# Title\n\nParagraph one.\n\nParagraph two."
    chunks=TextChunker(chunk_size=24,overlap=5).split(normalized)
    assert len(chunks)>=2
    assert all(content for content,_,_ in chunks)

@pytest.mark.asyncio
async def test_ingestion_normalizes_chunks_embeds_and_marks_ready():
    document=KnowledgeDocument(knowledge_base_key="architecture-references",title="Test",content="# Heading\n\n"+("OpenShift platform architecture. "*30),media_type="text/markdown")
    repo=Repo(document)
    service=KnowledgeIngestionService(repo,HashEmbeddingProvider(dimensions=384))
    result=await service.ingest(document.id,chunk_size=180,overlap=30,embed=True)
    assert result.status is KnowledgeDocumentStatus.READY
    assert result.chunks>1
    assert result.embedded_chunks==result.chunks
    assert result.embedding_model=="hash-embedding-v1"
    assert repo.document.status is KnowledgeDocumentStatus.READY
    assert len(repo.chunks[0].embedding)==384
    assert repo.chunks[0].metadata["chunking_strategy"]=="text-boundary-v1"
