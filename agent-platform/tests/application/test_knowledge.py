from uuid import UUID
import pytest
from agent_platform.application.knowledge import KnowledgeConflictError, KnowledgeService
from agent_platform.domain import KnowledgeBase, KnowledgeChunk, KnowledgeDocument

class Repo:
    def __init__(self): self.bases={}; self.documents={}; self.chunks={}
    async def list_bases(self): return list(self.bases.values())
    async def get_base(self,key): return self.bases.get(key)
    async def create_base(self,item): self.bases[item.key]=item; return item
    async def create_document(self,item): self.documents[item.id]=item; return item
    async def list_documents(self,key): return [d for d in self.documents.values() if d.knowledge_base_key==key]
    async def get_document(self,i): return self.documents.get(i)
    async def create_chunks(self,chunks): return chunks
    async def list_chunks(self,i): return []

@pytest.mark.asyncio
async def test_bootstrap_defaults_is_idempotent():
    service=KnowledgeService(Repo()); first=await service.bootstrap_defaults(); second=await service.bootstrap_defaults()
    assert len(first)==6 and second==[]

@pytest.mark.asyncio
async def test_upload_document_is_scoped_to_base():
    service=KnowledgeService(Repo()); await service.create_base(KnowledgeBase(key="architecture-references",name="Architecture"))
    doc=await service.upload_document("architecture-references",KnowledgeDocument(knowledge_base_key="ignored",title="ADR",content="Use GitOps"))
    assert doc.knowledge_base_key=="architecture-references"

@pytest.mark.asyncio
async def test_duplicate_base_is_rejected():
    service=KnowledgeService(Repo()); item=KnowledgeBase(key="case-studies",name="Case Studies"); await service.create_base(item)
    with pytest.raises(KnowledgeConflictError): await service.create_base(item)
