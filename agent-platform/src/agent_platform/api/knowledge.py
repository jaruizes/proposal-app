import json
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from agent_platform.api.dependencies import KnowledgeFileServiceDep, KnowledgeIngestionServiceDep, KnowledgeServiceDep
from agent_platform.application.file_ingestion import KnowledgeFileUploadError
from agent_platform.application.ingestion import KnowledgeIngestionError, KnowledgeIngestionResult
from agent_platform.application.knowledge import KnowledgeConflictError, KnowledgeNotFoundError
from agent_platform.domain import KnowledgeBase, KnowledgeChunk, KnowledgeDocument


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


class KnowledgeIngestRequest(BaseModel):
    chunk_size: int = Field(default=1200, gt=0, le=10000)
    overlap: int = Field(default=200, ge=0, le=5000)
    embed: bool = True


class KnowledgeFileUploadResponse(BaseModel):
    document: KnowledgeDocument
    ingestion: KnowledgeIngestionResult | None = None


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
    try: return await service.upload_document(key, KnowledgeDocument(knowledge_base_key=key, **payload.model_dump()))
    except KnowledgeNotFoundError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/knowledge-bases/{key}/files", response_model=KnowledgeFileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    key: str,
    service: KnowledgeFileServiceDep,
    file: UploadFile = File(...),
    metadata: str | None = Form(default=None),
    source_uri: str | None = Form(default=None),
    ingest: bool = Form(default=True),
    chunk_size: int = Form(default=1200),
    overlap: int = Form(default=200),
    embed: bool = Form(default=True),
):
    if chunk_size <= 0 or chunk_size > 10000:
        raise HTTPException(status_code=422, detail="chunk_size must be between 1 and 10000")
    if overlap < 0 or overlap >= chunk_size:
        raise HTTPException(status_code=422, detail="overlap must satisfy 0 <= overlap < chunk_size")
    parsed_metadata: dict = {}
    if metadata:
        try:
            parsed_metadata = json.loads(metadata)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="metadata must be a valid JSON object") from exc
        if not isinstance(parsed_metadata, dict):
            raise HTTPException(status_code=422, detail="metadata must be a JSON object")
    payload = await file.read()
    try:
        result = await service.upload(
            knowledge_base_key=key,
            filename=file.filename or "",
            payload=payload,
            declared_media_type=file.content_type,
            metadata=parsed_metadata,
            source_uri=source_uri,
            ingest=ingest,
            chunk_size=chunk_size,
            overlap=overlap,
            embed=embed,
        )
        return KnowledgeFileUploadResponse(document=result.document, ingestion=result.ingestion)
    except KnowledgeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (KnowledgeFileUploadError, KnowledgeIngestionError) as exc:
        message = str(exc)
        code = 413 if "exceeds the" in message and "MB limit" in message else 400
        raise HTTPException(status_code=code, detail=message) from exc


@router.get("/knowledge-documents/{document_id}", response_model=KnowledgeDocument)
async def get_document(document_id: UUID, service: KnowledgeServiceDep):
    try: return await service.get_document(document_id)
    except KnowledgeNotFoundError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/knowledge-documents/{document_id}/ingest", response_model=KnowledgeIngestionResult)
async def ingest_document(document_id: UUID, payload: KnowledgeIngestRequest, service: KnowledgeIngestionServiceDep):
    if payload.overlap >= payload.chunk_size: raise HTTPException(status_code=422, detail="overlap must be smaller than chunk_size")
    try: return await service.ingest(document_id, chunk_size=payload.chunk_size, overlap=payload.overlap, embed=payload.embed)
    except KnowledgeIngestionError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/knowledge-documents/{document_id}/chunks", response_model=list[KnowledgeChunk])
async def list_chunks(document_id: UUID, service: KnowledgeServiceDep):
    try: return await service.list_chunks(document_id)
    except KnowledgeNotFoundError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc
