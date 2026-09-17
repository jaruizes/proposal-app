from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from agent_platform.application.chunking import ChunkingStrategyName, FixedChunker, build_chunker
from agent_platform.application.embeddings import EmbeddingProvider, EmbeddingRequest
from agent_platform.application.repositories import KnowledgeRepository
from agent_platform.domain import KnowledgeChunk, KnowledgeDocumentStatus


SUPPORTED_TEXT_MEDIA_TYPES = {
    "text/plain",
    "text/markdown",
    "text/x-markdown",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class KnowledgeIngestionError(RuntimeError):
    pass


@dataclass(frozen=True)
class KnowledgeIngestionResult:
    document_id: UUID
    status: KnowledgeDocumentStatus
    normalized_chars: int
    chunks: int
    embedded_chunks: int
    embedding_model: str | None
    chunking_strategy: ChunkingStrategyName


class TextNormalizer:
    def normalize(self, content: str) -> str:
        text = content.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")
        text = "\n".join(line.rstrip() for line in text.split("\n"))
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


class TextChunker:
    """Backward-compatible adapter for the original fixed chunker contract."""

    def __init__(self, *, chunk_size: int = 1200, overlap: int = 200) -> None:
        self._delegate = FixedChunker(chunk_size=chunk_size, overlap=overlap)

    def split(self, text: str) -> list[tuple[str, int, int]]:
        return [(item.content, item.start, item.end) for item in self._delegate.split(text)]


class KnowledgeIngestionService:
    def __init__(
        self,
        repository: KnowledgeRepository,
        embedding_provider: EmbeddingProvider,
        *,
        normalizer: TextNormalizer | None = None,
    ) -> None:
        self._repository = repository
        self._embedding_provider = embedding_provider
        self._normalizer = normalizer or TextNormalizer()

    async def ingest(
        self,
        document_id: UUID,
        *,
        chunking_strategy: ChunkingStrategyName | str = ChunkingStrategyName.FIXED,
        chunk_size: int = 1200,
        overlap: int = 200,
        parent_size: int = 6000,
        child_size: int = 1200,
        child_overlap: int = 200,
        embed: bool = True,
    ) -> KnowledgeIngestionResult:
        document = await self._repository.get_document(document_id)
        if document is None:
            raise KnowledgeIngestionError(f"Knowledge document '{document_id}' not found")
        if document.media_type not in SUPPORTED_TEXT_MEDIA_TYPES:
            raise KnowledgeIngestionError(
                f"Unsupported media type '{document.media_type}'. Supported: {sorted(SUPPORTED_TEXT_MEDIA_TYPES)}"
            )

        normalized = self._normalizer.normalize(document.content)
        if not normalized:
            raise KnowledgeIngestionError("Document content is empty after normalization")

        try:
            selected_strategy = ChunkingStrategyName(chunking_strategy)
        except ValueError as exc:
            raise KnowledgeIngestionError(f"Unsupported chunking strategy '{chunking_strategy}'") from exc

        await self._repository.update_document(
            document.model_copy(update={"status": KnowledgeDocumentStatus.PROCESSING})
        )
        try:
            chunker = build_chunker(
                selected_strategy,
                chunk_size=chunk_size,
                overlap=overlap,
                parent_size=parent_size,
                child_size=child_size,
                child_overlap=child_overlap,
            )
            candidates = chunker.split(normalized)
            chunks = [
                KnowledgeChunk(
                    document_id=document.id,
                    ordinal=ordinal,
                    content=candidate.content,
                    metadata={
                        "knowledge_base_key": document.knowledge_base_key,
                        "title": document.title,
                        "media_type": document.media_type,
                        "source_uri": document.source_uri,
                        "char_start": candidate.start,
                        "char_end": candidate.end,
                        **candidate.metadata,
                    },
                )
                for ordinal, candidate in enumerate(candidates)
            ]

            embedding_model = None
            embedded_chunks = 0
            embeddable_indexes = [index for index, candidate in enumerate(candidates) if candidate.embed]
            if embed and embeddable_indexes:
                result = await self._embedding_provider.embed(
                    EmbeddingRequest(texts=[chunks[index].content for index in embeddable_indexes])
                )
                if len(result.vectors) != len(embeddable_indexes):
                    raise KnowledgeIngestionError("Embedding provider returned an unexpected vector count")
                for index, vector in zip(embeddable_indexes, result.vectors, strict=True):
                    chunks[index] = chunks[index].model_copy(
                        update={"embedding": vector, "embedding_model": result.model}
                    )
                embedding_model = result.model
                embedded_chunks = len(embeddable_indexes)

            await self._repository.replace_chunks(document.id, chunks)
            ready = document.model_copy(update={"status": KnowledgeDocumentStatus.READY})
            await self._repository.update_document(ready)
            return KnowledgeIngestionResult(
                document_id=document.id,
                status=KnowledgeDocumentStatus.READY,
                normalized_chars=len(normalized),
                chunks=len(chunks),
                embedded_chunks=embedded_chunks,
                embedding_model=embedding_model,
                chunking_strategy=selected_strategy,
            )
        except Exception as exc:
            failed = document.model_copy(update={"status": KnowledgeDocumentStatus.FAILED})
            await self._repository.update_document(failed)
            if isinstance(exc, KnowledgeIngestionError):
                raise
            raise KnowledgeIngestionError(str(exc)) from exc
