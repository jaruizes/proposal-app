from __future__ import annotations

from dataclasses import dataclass

from agent_platform.application.document_parsers import DocumentParseError, DocumentParserRegistry
from agent_platform.application.ingestion import KnowledgeIngestionResult, KnowledgeIngestionService
from agent_platform.application.knowledge import KnowledgeService
from agent_platform.domain import KnowledgeDocument


MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class KnowledgeFileUploadError(RuntimeError):
    pass


@dataclass(frozen=True)
class KnowledgeFileUploadResult:
    document: KnowledgeDocument
    ingestion: KnowledgeIngestionResult | None


class KnowledgeFileService:
    def __init__(
        self,
        knowledge_service: KnowledgeService,
        ingestion_service: KnowledgeIngestionService,
        parser_registry: DocumentParserRegistry | None = None,
    ) -> None:
        self._knowledge_service = knowledge_service
        self._ingestion_service = ingestion_service
        self._parsers = parser_registry or DocumentParserRegistry()

    async def upload(
        self,
        *,
        knowledge_base_key: str,
        filename: str,
        payload: bytes,
        declared_media_type: str | None,
        metadata: dict,
        source_uri: str | None,
        ingest: bool,
        chunk_size: int,
        overlap: int,
        embed: bool,
    ) -> KnowledgeFileUploadResult:
        await self._knowledge_service.get_base(knowledge_base_key)
        if not filename:
            raise KnowledgeFileUploadError("Uploaded file must have a filename")
        if not payload:
            raise KnowledgeFileUploadError("Uploaded file is empty")
        if len(payload) > MAX_UPLOAD_BYTES:
            raise KnowledgeFileUploadError(f"Uploaded file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit")
        try:
            parsed = self._parsers.parse(payload, filename=filename, declared_media_type=declared_media_type)
        except DocumentParseError as exc:
            raise KnowledgeFileUploadError(str(exc)) from exc

        document = KnowledgeDocument(
            knowledge_base_key=knowledge_base_key,
            title=filename,
            content=parsed.content,
            media_type=parsed.media_type,
            source_uri=source_uri or f"upload://{filename}",
            metadata={
                **metadata,
                "upload": {
                    "original_filename": filename,
                    "declared_media_type": declared_media_type,
                    "byte_size": len(payload),
                    **parsed.metadata,
                },
            },
        )
        stored = await self._knowledge_service.upload_document(knowledge_base_key, document)
        ingestion = None
        if ingest:
            ingestion = await self._ingestion_service.ingest(
                stored.id,
                chunk_size=chunk_size,
                overlap=overlap,
                embed=embed,
            )
        return KnowledgeFileUploadResult(document=stored, ingestion=ingestion)
