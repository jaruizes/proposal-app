from uuid import UUID
from agent_platform.application.repositories import KnowledgeRepository
from agent_platform.domain import DEFAULT_KNOWLEDGE_BASES, KnowledgeBase, KnowledgeDocument, KnowledgeDocumentStatus
class KnowledgeNotFoundError(LookupError): pass
class KnowledgeConflictError(RuntimeError): pass
class KnowledgeService:
    def __init__(self,repository:KnowledgeRepository)->None: self._repository=repository
    async def list_bases(self): return await self._repository.list_bases()
    async def get_base(self,key:str)->KnowledgeBase:
        item=await self._repository.get_base(key)
        if item is None: raise KnowledgeNotFoundError(f"Knowledge base '{key}' not found")
        return item
    async def create_base(self,item:KnowledgeBase)->KnowledgeBase:
        if await self._repository.get_base(item.key): raise KnowledgeConflictError(f"Knowledge base '{item.key}' already exists")
        return await self._repository.create_base(item)
    async def bootstrap_defaults(self):
        created=[]
        for key,name,description in DEFAULT_KNOWLEDGE_BASES:
            if await self._repository.get_base(key) is None: created.append(await self._repository.create_base(KnowledgeBase(key=key,name=name,description=description)))
        return created
    async def upload_document(self,knowledge_base_key:str,document:KnowledgeDocument)->KnowledgeDocument:
        await self.get_base(knowledge_base_key)
        item=document.model_copy(update={"knowledge_base_key":knowledge_base_key})
        if item.version==1 and item.family_id!=item.id and item.previous_version_id is None:
            item=item.model_copy(update={"family_id":item.id})
        return await self._repository.create_document(item)
    async def list_documents(self,knowledge_base_key:str):
        await self.get_base(knowledge_base_key)
        return await self._repository.list_documents(knowledge_base_key)
    async def get_document(self,document_id:UUID):
        item=await self._repository.get_document(document_id)
        if item is None: raise KnowledgeNotFoundError(f"Knowledge document '{document_id}' not found")
        return item
    async def list_chunks(self,document_id:UUID):
        await self.get_document(document_id); return await self._repository.list_chunks(document_id)
    async def list_versions(self,document_id:UUID):
        item=await self.get_document(document_id); return await self._repository.list_versions(item.family_id)
    async def archive(self,document_id:UUID):
        item=await self.get_document(document_id)
        if item.status is KnowledgeDocumentStatus.ARCHIVED:return item
        return await self._repository.update_document(item.model_copy(update={"status":KnowledgeDocumentStatus.ARCHIVED}))
    async def restore(self,document_id:UUID):
        item=await self.get_document(document_id)
        versions=await self._repository.list_versions(item.family_id)
        for version in versions:
            if version.id!=item.id and version.status is KnowledgeDocumentStatus.READY:
                await self._repository.update_document(version.model_copy(update={"status":KnowledgeDocumentStatus.SUPERSEDED}))
        return await self._repository.update_document(item.model_copy(update={"status":KnowledgeDocumentStatus.READY}))
    async def supersede(self,document_id:UUID):
        item=await self.get_document(document_id)
        return await self._repository.update_document(item.model_copy(update={"status":KnowledgeDocumentStatus.SUPERSEDED}))
    async def delete(self,document_id:UUID):
        item=await self.get_document(document_id)
        family_id=item.family_id
        was_active=item.status is KnowledgeDocumentStatus.READY
        await self._repository.delete_document(document_id)
        if was_active:
            remaining=await self._repository.list_versions(family_id)
            candidate=next((v for v in remaining if v.status in {KnowledgeDocumentStatus.SUPERSEDED,KnowledgeDocumentStatus.ARCHIVED}),None)
            if candidate is not None:
                await self._repository.update_document(candidate.model_copy(update={"status":KnowledgeDocumentStatus.READY}))
        return None
