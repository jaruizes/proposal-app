from __future__ import annotations

from dataclasses import dataclass

from agent_platform.application.chunking import ChunkingStrategyName
from agent_platform.application.document_parsers import DocumentParseError, DocumentParserRegistry
from agent_platform.application.ingestion import KnowledgeIngestionResult, KnowledgeIngestionService
from agent_platform.application.knowledge import KnowledgeService
from agent_platform.application.knowledge_classification import DeterministicKnowledgeClassifier
from agent_platform.application.metadata_enrichment import MetadataEnrichmentProfile
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
        classifier: DeterministicKnowledgeClassifier | None = None,
    ) -> None:
        self._knowledge_service = knowledge_service
        self._ingestion_service = ingestion_service
        self._parsers = parser_registry or DocumentParserRegistry()
        self._classifier = classifier or DeterministicKnowledgeClassifier()

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
        chunking_strategy: ChunkingStrategyName | str = ChunkingStrategyName.FIXED,
        chunk_size: int = 1200,
        overlap: int = 200,
        parent_size: int = 6000,
        child_size: int = 1200,
        child_overlap: int = 200,
        embed: bool = True,
        metadata_enrichment: MetadataEnrichmentProfile | str = MetadataEnrichmentProfile.STANDARD,
        max_keywords: int = 8,
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

        classified_metadata = dict(metadata)
        classified_metadata["classification"] = self._classifier.classify(knowledge_base_key, classified_metadata)

        document = KnowledgeDocument(
            knowledge_base_key=knowledge_base_key,
            title=filename,
            content=parsed.content,
            media_type=parsed.media_type,
            source_uri=source_uri or f"upload://{filename}",
            metadata={
                **classified_metadata,
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
        return KnowledgeFileUploadResult(document=stored, ingestion=ingestion)
