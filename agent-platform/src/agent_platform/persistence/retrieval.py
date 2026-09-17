from __future__ import annotations

from sqlalchemy import func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.application.retrieval import RetrievalCandidate
from agent_platform.domain.retrieval import RetrievalQuery
from agent_platform.persistence.models import KnowledgeBaseRecord, KnowledgeChunkRecord, KnowledgeDocumentRecord


class PostgresKnowledgeSearchBackend:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _base_filters(self, query: RetrievalQuery):
        filters = [
            KnowledgeDocumentRecord.status == "READY",
            KnowledgeBaseRecord.enabled.is_(True),
        ]
        if query.filters.knowledge_base_keys:
            filters.append(KnowledgeDocumentRecord.knowledge_base_key.in_(query.filters.knowledge_base_keys))
        if query.filters.document_ids:
            filters.append(KnowledgeDocumentRecord.id.in_(query.filters.document_ids))
        if query.filters.metadata:
            filters.append(KnowledgeChunkRecord.metadata_json.contains(query.filters.metadata))
        if query.filters.document_metadata:
            filters.append(KnowledgeDocumentRecord.metadata_json.contains(query.filters.document_metadata))
        hierarchy_level = KnowledgeChunkRecord.metadata_json["hierarchy_level"].astext
        filters.append(or_(hierarchy_level.is_(None), hierarchy_level != "parent"))
        return filters

    def _candidate(self, row, score: float) -> RetrievalCandidate:
        chunk, document = row[0], row[1]
        return RetrievalCandidate(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            knowledge_base_key=document.knowledge_base_key,
            title=document.title,
            content=chunk.content,
            score=float(score),
            metadata=chunk.metadata_json or {},
            source_uri=document.source_uri,
        )

    async def vector_search(self, *, query_vector, embedding_model, query, limit):
        distance = KnowledgeChunkRecord.embedding.cosine_distance(query_vector)
        score = (literal(1.0) - distance).label("score")
        statement = (
            select(KnowledgeChunkRecord, KnowledgeDocumentRecord, score)
            .join(KnowledgeDocumentRecord, KnowledgeDocumentRecord.id == KnowledgeChunkRecord.document_id)
            .join(KnowledgeBaseRecord, KnowledgeBaseRecord.key == KnowledgeDocumentRecord.knowledge_base_key)
            .where(
                KnowledgeChunkRecord.embedding.is_not(None),
                KnowledgeChunkRecord.embedding_model == embedding_model,
                *self._base_filters(query),
            )
            .order_by(distance.asc(), KnowledgeChunkRecord.id.asc())
            .limit(limit)
        )
        rows = (await self._session.execute(statement)).all()
        return [self._candidate(row, row[2]) for row in rows]

    async def keyword_search(self, *, query, limit):
        vector = func.to_tsvector("simple", KnowledgeChunkRecord.content)
        ts_query = func.websearch_to_tsquery("simple", query.text)
        rank = func.ts_rank_cd(vector, ts_query).label("score")
        statement = (
            select(KnowledgeChunkRecord, KnowledgeDocumentRecord, rank)
            .join(KnowledgeDocumentRecord, KnowledgeDocumentRecord.id == KnowledgeChunkRecord.document_id)
            .join(KnowledgeBaseRecord, KnowledgeBaseRecord.key == KnowledgeDocumentRecord.knowledge_base_key)
            .where(vector.op("@@")(ts_query), *self._base_filters(query))
            .order_by(rank.desc(), KnowledgeChunkRecord.id.asc())
            .limit(limit)
        )
        rows = (await self._session.execute(statement)).all()
        return [self._candidate(row, row[2]) for row in rows]

    async def parent_for(self, candidate: RetrievalCandidate) -> RetrievalCandidate | None:
        if candidate.metadata.get("hierarchy_level") != "child":
            return None
        parent_index = candidate.metadata.get("parent_index")
        if parent_index is None:
            return None
        parent_level = KnowledgeChunkRecord.metadata_json["hierarchy_level"].astext
        parent_value = KnowledgeChunkRecord.metadata_json["parent_index"].astext
        statement = (
            select(KnowledgeChunkRecord, KnowledgeDocumentRecord)
            .join(KnowledgeDocumentRecord, KnowledgeDocumentRecord.id == KnowledgeChunkRecord.document_id)
            .where(
                KnowledgeChunkRecord.document_id == candidate.document_id,
                parent_level == "parent",
                parent_value == str(parent_index),
            )
            .limit(1)
        )
        row = (await self._session.execute(statement)).first()
        if row is None:
            return None
        return self._candidate((row[0], row[1]), candidate.score)
