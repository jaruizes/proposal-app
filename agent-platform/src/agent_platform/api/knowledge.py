from uuid import UUID
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from agent_platform.api.dependencies import KnowledgeServiceDep
from agent_platform.application.knowledge import KnowledgeConflictError, KnowledgeNotFoundError
from agent_platform.domain import KnowledgeBase, KnowledgeDocument

router = APIRouter(prefix="/v1", tags=["knowledge"])

class KnowledgeBaseCreate(BaseModel):
    key: str
    name: str
    description: str = ""
    metadata: dict = Field(default_factory=dict)
    enabled: bool = True

class KnowledgeDocumentCreate(BaseModel):
    title: str
    content: str
    media_type: str = "text/plain"
    source_uri: str | None = None
    metadata: dict = Field(default_factory=dict)

@router.get("/knowledge-bases", response_model=list[KnowledgeBase])
async def list_bases(service: KnowledgeServiceDep): return await service.list_bases()

@router.post("/knowledge-bases", response_model=KnowledgeBase, status_code=status.HTTP_201_CREATED)
async def create_base(payload: KnowledgeBaseCreate, service: KnowledgeServiceDep):
    try: return await service.create_base(KnowledgeBase(**payload.model_dump()))
    except KnowledgeConflictError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.post("/knowledge-bases/bootstrap", response_model=list[KnowledgeBase])
async def bootstrap(service: KnowledgeServiceDep): return await service.bootstrap_defaults()

@router.get("/knowledge-bases/{key}", response_model=KnowledgeBase)
async def get_base(key: str, service: KnowledgeServiceDep):
    try: return await service.get_base(key)
    except KnowledgeNotFoundError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc

@router.get("/knowledge-bases/{key}/documents", response_model=list[KnowledgeDocument])
async def list_documents(key: str, service: KnowledgeServiceDep):
    try: return await service.list_documents(key)
    except KnowledgeNotFoundError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc

@router.post("/knowledge-bases/{key}/documents", response_model=KnowledgeDocument, status_code=status.HTTP_201_CREATED)
async def upload_document(key: str, payload: KnowledgeDocumentCreate, service: KnowledgeServiceDep):
    try:
        return await service.upload_document(key, KnowledgeDocument(knowledge_base_key=key, **payload.model_dump()))
    except KnowledgeNotFoundError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc

@router.get("/knowledge-documents/{document_id}", response_model=KnowledgeDocument)
async def get_document(document_id: UUID, service: KnowledgeServiceDep):
    try: return await service.get_document(document_id)
    except KnowledgeNotFoundError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc
