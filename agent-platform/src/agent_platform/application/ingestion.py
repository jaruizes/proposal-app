from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from agent_platform.application.cache import CacheService
from agent_platform.application.chunking import ChunkingStrategyName, FixedChunker, build_chunker
from agent_platform.application.embeddings import EmbeddingProvider, EmbeddingRequest
from agent_platform.application.metadata_enrichment import DeterministicMetadataEnricher, MetadataEnricher, MetadataEnrichmentProfile
from agent_platform.application.repositories import KnowledgeRepository
from agent_platform.domain import KnowledgeChunk, KnowledgeDocumentStatus

SUPPORTED_TEXT_MEDIA_TYPES={"text/plain","text/markdown","text/x-markdown","application/pdf","application/vnd.openxmlformats-officedocument.wordprocessingml.document"}

class KnowledgeIngestionError(RuntimeError):pass

@dataclass(frozen=True)
class KnowledgeIngestionResult:
    document_id:UUID;status:KnowledgeDocumentStatus;normalized_chars:int;chunks:int;embedded_chunks:int;embedding_model:str|None;chunking_strategy:ChunkingStrategyName;metadata_enrichment:MetadataEnrichmentProfile=MetadataEnrichmentProfile.STANDARD

@dataclass(frozen=True)
class KnowledgeMetadataEnrichmentResult:
    document_id:UUID;profile:MetadataEnrichmentProfile;document_metadata:dict;chunks_enriched:int

class TextNormalizer:
    def normalize(self,content:str)->str:
        text=content.replace("\ufeff","").replace("\r\n","\n").replace("\r","\n");text="\n".join(line.rstrip() for line in text.split("\n"));return re.sub(r"\n{3,}","\n\n",text).strip()

class TextChunker:
    def __init__(self,*,chunk_size:int=1200,overlap:int=200)->None:self._delegate=FixedChunker(chunk_size=chunk_size,overlap=overlap)
    def split(self,text:str)->list[tuple[str,int,int]]:return[(item.content,item.start,item.end) for item in self._delegate.split(text)]

class KnowledgeIngestionService:
    def __init__(self,repository:KnowledgeRepository,embedding_provider:EmbeddingProvider,*,normalizer:TextNormalizer|None=None,metadata_enricher:MetadataEnricher|None=None,cache:CacheService|None=None,ontology_service=None)->None:
        self._repository=repository;self._embedding_provider=embedding_provider;self._normalizer=normalizer or TextNormalizer();self._metadata_enricher=metadata_enricher or DeterministicMetadataEnricher();self._cache=cache;self._ontology_service=ontology_service

    async def _invalidate_knowledge_cache(self)->None:
        if self._cache is None:return
        await self._cache.invalidate_namespace("retrieval");await self._cache.invalidate_namespace("cognitive-rag")

    async def ingest(self,document_id:UUID,*,chunking_strategy:ChunkingStrategyName|str=ChunkingStrategyName.FIXED,chunk_size:int=1200,overlap:int=200,parent_size:int=6000,child_size:int=1200,child_overlap:int=200,embed:bool=True,metadata_enrichment:MetadataEnrichmentProfile|str=MetadataEnrichmentProfile.STANDARD,max_keywords:int=8)->KnowledgeIngestionResult:
        document=await self._repository.get_document(document_id)
        if document is None:raise KnowledgeIngestionError(f"Knowledge document '{document_id}' not found")
        if document.media_type not in SUPPORTED_TEXT_MEDIA_TYPES:raise KnowledgeIngestionError(f"Unsupported media type '{document.media_type}'. Supported: {sorted(SUPPORTED_TEXT_MEDIA_TYPES)}")
        normalized=self._normalizer.normalize(document.content)
        if not normalized:raise KnowledgeIngestionError("Document content is empty after normalization")
        try:selected_strategy=ChunkingStrategyName(chunking_strategy);selected_enrichment=MetadataEnrichmentProfile(metadata_enrichment)
        except ValueError as exc:raise KnowledgeIngestionError(str(exc)) from exc
        if not 0<=max_keywords<=50:raise KnowledgeIngestionError("max_keywords must be between 0 and 50")
        await self._repository.update_document(document.model_copy(update={"status":KnowledgeDocumentStatus.PROCESSING}))
        try:
            document_enrichment=await self._metadata_enricher.enrich_document(document,normalized,profile=selected_enrichment,max_keywords=max_keywords)
            enriched_document=document.model_copy(update={"metadata":self._merge_enrichment(document.metadata,document_enrichment),"status":KnowledgeDocumentStatus.PROCESSING});await self._repository.update_document(enriched_document)
            candidates=build_chunker(selected_strategy,chunk_size=chunk_size,overlap=overlap,parent_size=parent_size,child_size=child_size,child_overlap=child_overlap).split(normalized)
            chunks=[]
            for ordinal,candidate in enumerate(candidates):
                base_chunk=KnowledgeChunk(document_id=document.id,ordinal=ordinal,content=candidate.content,metadata={"knowledge_base_key":document.knowledge_base_key,"title":document.title,"media_type":document.media_type,"source_uri":document.source_uri,"char_start":candidate.start,"char_end":candidate.end,**candidate.metadata})
                enrichment=await self._metadata_enricher.enrich_chunk(enriched_document,base_chunk,profile=selected_enrichment,max_keywords=max_keywords,document_enrichment=document_enrichment)
                chunks.append(base_chunk.model_copy(update={"metadata":self._merge_enrichment(base_chunk.metadata,enrichment)}))
            embedding_model=None;embedded_chunks=0;embeddable=[index for index,candidate in enumerate(candidates) if candidate.embed]
            if embed and embeddable:
                result=await self._embedding_provider.embed(EmbeddingRequest(texts=[chunks[index].content for index in embeddable]))
                if len(result.vectors)!=len(embeddable):raise KnowledgeIngestionError("Embedding provider returned an unexpected vector count")
                for index,vector in zip(embeddable,result.vectors,strict=True):chunks[index]=chunks[index].model_copy(update={"embedding":vector,"embedding_model":result.model})
                embedding_model=result.model;embedded_chunks=len(embeddable)
            await self._repository.replace_chunks(document.id,chunks);await self._repository.update_document(enriched_document.model_copy(update={"status":KnowledgeDocumentStatus.READY}))
            if self._ontology_service is not None:
                try:await self._ontology_service.tag_document(document.id)
                except Exception:pass
            await self._invalidate_knowledge_cache()
            return KnowledgeIngestionResult(document_id=document.id,status=KnowledgeDocumentStatus.READY,normalized_chars=len(normalized),chunks=len(chunks),embedded_chunks=embedded_chunks,embedding_model=embedding_model,chunking_strategy=selected_strategy,metadata_enrichment=selected_enrichment)
        except Exception as exc:
            await self._repository.update_document(document.model_copy(update={"status":KnowledgeDocumentStatus.FAILED}))
            if isinstance(exc,KnowledgeIngestionError):raise
            raise KnowledgeIngestionError(str(exc)) from exc

    async def enrich_existing(self,document_id:UUID,*,metadata_enrichment:MetadataEnrichmentProfile|str=MetadataEnrichmentProfile.STANDARD,max_keywords:int=8)->KnowledgeMetadataEnrichmentResult:
        document=await self._repository.get_document(document_id)
        if document is None:raise KnowledgeIngestionError(f"Knowledge document '{document_id}' not found")
        try:selected=MetadataEnrichmentProfile(metadata_enrichment)
        except ValueError as exc:raise KnowledgeIngestionError(f"Unsupported metadata enrichment profile '{metadata_enrichment}'") from exc
        if not 0<=max_keywords<=50:raise KnowledgeIngestionError("max_keywords must be between 0 and 50")
        normalized=self._normalizer.normalize(document.content);doc_enrichment=await self._metadata_enricher.enrich_document(document,normalized,profile=selected,max_keywords=max_keywords)
        updated=document.model_copy(update={"metadata":self._merge_enrichment(document.metadata,doc_enrichment)});await self._repository.update_document(updated)
        chunks=await self._repository.list_chunks(document_id);enriched=[]
        for chunk in chunks:
            metadata=await self._metadata_enricher.enrich_chunk(updated,chunk,profile=selected,max_keywords=max_keywords,document_enrichment=doc_enrichment);enriched.append(chunk.model_copy(update={"metadata":self._merge_enrichment(chunk.metadata,metadata)}))
        if chunks:await self._repository.replace_chunks(document_id,enriched)
        if self._ontology_service is not None:
            try:await self._ontology_service.tag_document(document_id)
            except Exception:pass
        await self._invalidate_knowledge_cache()
        return KnowledgeMetadataEnrichmentResult(document_id=document_id,profile=selected,document_metadata=doc_enrichment,chunks_enriched=len(enriched))

    @staticmethod
    def _merge_enrichment(metadata:dict,enrichment:dict)->dict:
        merged=dict(metadata)
        if enrichment:merged["enrichment"]=enrichment
        else:merged.pop("enrichment",None)
        return merged
