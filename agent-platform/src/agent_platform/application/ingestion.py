from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

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


class TextNormalizer:
    def normalize(self, content: str) -> str:
        text = content.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")
        text = "\n".join(line.rstrip() for line in text.split("\n"))
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


class TextChunker:
    def __init__(self, *, chunk_size: int = 1200, overlap: int = 200) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str) -> list[tuple[str, int, int]]:
        if not text:
            return []
        chunks: list[tuple[str, int, int]] = []
        start = 0
        length = len(text)
        while start < length:
            hard_end = min(start + self.chunk_size, length)
            end = hard_end
            if hard_end < length:
                paragraph_break = text.rfind("\n\n", start + self.chunk_size // 2, hard_end)
                sentence_break = text.rfind(". ", start + self.chunk_size // 2, hard_end)
                if paragraph_break > start:
                    end = paragraph_break + 2
                elif sentence_break > start:
                    end = sentence_break + 2
            content = text[start:end].strip()
            if content:
                chunks.append((content, start, end))
            if end >= length:
                break
            start = max(end - self.overlap, start + 1)
        return chunks


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
        chunk_size: int = 1200,
        overlap: int = 200,
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

        await self._repository.update_document(
            document.model_copy(update={"status": KnowledgeDocumentStatus.PROCESSING})
        )
        try:
            chunker = TextChunker(chunk_size=chunk_size, overlap=overlap)
            raw_chunks = chunker.split(normalized)
            chunks = [
                KnowledgeChunk(
                    document_id=document.id,
                    ordinal=ordinal,
                    content=content,
                    metadata={
                        "knowledge_base_key": document.knowledge_base_key,
                        "title": document.title,
                        "media_type": document.media_type,
                        "source_uri": document.source_uri,
                        "char_start": start,
                        "char_end": end,
                        "chunking_strategy": "text-boundary-v1",
                    },
                )
                for ordinal, (content, start, end) in enumerate(raw_chunks)
            ]

            embedding_model = None
            embedded_chunks = 0
            if embed and chunks:
                result = await self._embedding_provider.embed(
                    EmbeddingRequest(texts=[chunk.content for chunk in chunks])
                )
                if len(result.vectors) != len(chunks):
                    raise KnowledgeIngestionError("Embedding provider returned an unexpected vector count")
                chunks = [
                    chunk.model_copy(update={"embedding": vector, "embedding_model": result.model})
                    for chunk, vector in zip(chunks, result.vectors, strict=True)
                ]
                embedding_model = result.model
                embedded_chunks = len(chunks)

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
            )
        except Exception:
            failed = document.model_copy(update={"status": KnowledgeDocumentStatus.FAILED})
            await self._repository.update_document(failed)
            raise
