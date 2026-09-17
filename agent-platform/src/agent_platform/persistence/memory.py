from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.domain.memory import MemoryEntry, MemoryKind, MemoryRecall, MemoryScopeType
from agent_platform.persistence.models import MemoryRecord


def _to_domain(record: MemoryRecord) -> MemoryEntry:
    return MemoryEntry(
        id=record.id,
        scope_type=MemoryScopeType(record.scope_type),
        scope_key=record.scope_key,
        kind=MemoryKind(record.kind),
        content=record.content,
        agent_key=record.agent_key,
        skill_key=record.skill_key,
        metadata=record.metadata_json or {},
        importance=record.importance,
        active=record.active,
        expires_at=record.expires_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


class PostgresMemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, entry: MemoryEntry) -> MemoryEntry:
        self._session.add(
            MemoryRecord(
                id=entry.id,
                scope_type=entry.scope_type.value,
                scope_key=entry.scope_key,
                kind=entry.kind.value,
                content=entry.content,
                agent_key=entry.agent_key,
                skill_key=entry.skill_key,
                metadata_json=entry.metadata,
                importance=entry.importance,
                active=entry.active,
                expires_at=entry.expires_at,
                created_at=entry.created_at,
                updated_at=entry.updated_at,
            )
        )
        await self._session.commit()
        return entry

    async def get(self, memory_id: UUID) -> MemoryEntry | None:
        record = await self._session.get(MemoryRecord, memory_id)
        return _to_domain(record) if record else None

    async def recall(self, query: MemoryRecall) -> list[MemoryEntry]:
        scope_filters = [
            (MemoryRecord.scope_type == scope.type.value) & (MemoryRecord.scope_key == scope.key)
            for scope in query.scopes
        ]
        statement = select(MemoryRecord).where(MemoryRecord.active.is_(True), or_(*scope_filters))
        if query.kinds:
            statement = statement.where(MemoryRecord.kind.in_([kind.value for kind in query.kinds]))
        if query.agent_key:
            statement = statement.where(or_(MemoryRecord.agent_key.is_(None), MemoryRecord.agent_key == query.agent_key))
        if query.skill_key:
            statement = statement.where(or_(MemoryRecord.skill_key.is_(None), MemoryRecord.skill_key == query.skill_key))
        if query.min_importance > 0:
            statement = statement.where(MemoryRecord.importance >= query.min_importance)
        if not query.include_expired:
            now = datetime.now(timezone.utc)
            statement = statement.where(or_(MemoryRecord.expires_at.is_(None), MemoryRecord.expires_at > now))
        statement = statement.order_by(MemoryRecord.importance.desc(), MemoryRecord.created_at.desc()).limit(query.limit)
        result = await self._session.execute(statement)
        return [_to_domain(record) for record in result.scalars().all()]

    async def forget(self, memory_id: UUID) -> bool:
        record = await self._session.get(MemoryRecord, memory_id)
        if record is None:
            return False
        record.active = False
        record.updated_at = datetime.now(timezone.utc)
        await self._session.commit()
        return True
