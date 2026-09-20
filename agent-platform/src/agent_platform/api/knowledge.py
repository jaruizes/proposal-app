import json
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field

from agent_platform.api.dependencies import KnowledgeFileServiceDep, KnowledgeIngestionServiceDep, KnowledgeServiceDep
from agent_platform.application.chunking import ChunkingStrategyName
from agent_platform.application.file_ingestion import KnowledgeFileUploadError
from agent_platform.application.ingestion import (
    KnowledgeIngestionError,
    KnowledgeIngestionResult,
    KnowledgeMetadataEnrichmentResult,
)
from agent_platform.application.knowledge import KnowledgeConflictError, KnowledgeNotFoundError
from agent_platform.application.metadata_enrichment import MetadataEnrichmentProfile
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
    chunking_strategy: ChunkingStrategyName = ChunkingStrategyName.FIXED
    chunk_size: int = Field(default=1200, gt=0, le=10000)
    overlap: int = Field(default=200, ge=0, le=5000)
    parent_size: int = Field(default=6000, gt=0, le=50000)
    child_size: int = Field(default=1200, gt=0, le=10000)
    child_overlap: int = Field(default=200, ge=0, le=5000)
    embed: bool = True
    metadata_enrichment: MetadataEnrichmentProfile = MetadataEnrichmentProfile.STANDARD
    max_keywords: int = Field(default=8, ge=0, le=50)


class KnowledgeEnrichRequest(BaseModel):
    metadata_enrichment: MetadataEnrichmentProfile = MetadataEnrichmentProfile.STANDARD
    max_keywords: int = Field(default=8, ge=0, le=50)


class KnowledgeFileUploadResponse(BaseModel):
    document: KnowledgeDocument
    ingestion: KnowledgeIngestionResult | None = None


def _validate_chunking(
    strategy: ChunkingStrategyName,
    chunk_size: int,
    overlap: int,
    parent_size: int,
    child_size: int,
    child_overlap: int,
) -> None:
    if strategy is ChunkingStrategyName.HIERARCHICAL:
        if child_overlap >= child_size:
            raise HTTPException(status_code=422, detail="child_overlap must be smaller than child_size")
        if child_size >= parent_size:
            raise HTTPException(status_code=422, detail="child_size must be smaller than parent_size")
    elif overlap >= chunk_size:
        raise HTTPException(status_code=422, detail="overlap must be smaller than chunk_size")


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
    chunking_strategy: ChunkingStrategyName = Form(default=ChunkingStrategyName.FIXED),
    chunk_size: int = Form(default=1200),
    overlap: int = Form(default=200),
    parent_size: int = Form(default=6000),
    child_size: int = Form(default=1200),
    child_overlap: int = Form(default=200),
    embed: bool = Form(default=True),
    metadata_enrichment: MetadataEnrichmentProfile = Form(default=MetadataEnrichmentProfile.STANDARD),
    max_keywords: int = Form(default=8),
):
    if not 1 <= chunk_size <= 10000:
        raise HTTPException(status_code=422, detail="chunk_size must be between 1 and 10000")
    if not 1 <= parent_size <= 50000:
        raise HTTPException(status_code=422, detail="parent_size must be between 1 and 50000")
    if not 1 <= child_size <= 10000:
        raise HTTPException(status_code=422, detail="child_size must be between 1 and 10000")
    if overlap < 0 or child_overlap < 0:
        raise HTTPException(status_code=422, detail="overlap values must be >= 0")
    if not 0 <= max_keywords <= 50:
        raise HTTPException(status_code=422, detail="max_keywords must be between 0 and 50")
    _validate_chunking(chunking_strategy, chunk_size, overlap, parent_size, child_size, child_overlap)
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
            chunking_strategy=chunking_strategy,
            chunk_size=chunk_size,
            overlap=overlap,
            parent_size=parent_size,
            child_size=child_size,
            child_overlap=child_overlap,
            embed=embed,
            metadata_enrichment=metadata_enrichment,
            max_keywords=max_keywords,
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
    _validate_chunking(payload.chunking_strategy, payload.chunk_size, payload.overlap, payload.parent_size, payload.child_size, payload.child_overlap)
    try:
        return await service.ingest(
            document_id,
            chunking_strategy=payload.chunking_strategy,
            chunk_size=payload.chunk_size,
            overlap=payload.overlap,
            parent_size=payload.parent_size,
            child_size=payload.child_size,
            child_overlap=payload.child_overlap,
            embed=payload.embed,
            metadata_enrichment=payload.metadata_enrichment,
            max_keywords=payload.max_keywords,
        )
    except KnowledgeIngestionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/knowledge-documents/{document_id}/enrich", response_model=KnowledgeMetadataEnrichmentResult)
async def enrich_document(document_id: UUID, payload: KnowledgeEnrichRequest, service: KnowledgeIngestionServiceDep):
    try:
        return await service.enrich_existing(
            document_id,
            metadata_enrichment=payload.metadata_enrichment,
            max_keywords=payload.max_keywords,
        )
    except KnowledgeIngestionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/knowledge-documents/{document_id}/chunks", response_model=list[KnowledgeChunk])
async def list_chunks(
    document_id: UUID,
    service: KnowledgeServiceDep,
    offset: int = Query(default=0, ge=0),
    limit: int | None = Query(default=None, ge=1, le=500),
):
    try:
        chunks = await service.list_chunks(document_id)
        return chunks[offset:] if limit is None else chunks[offset:offset + limit]
    except KnowledgeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
