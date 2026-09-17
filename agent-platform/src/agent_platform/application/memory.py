from __future__ import annotations

from typing import Protocol
from uuid import UUID

from agent_platform.domain.memory import MemoryEntry, MemoryKind, MemoryRecall, MemoryScopeType, MemoryWrite


class MemoryRepository(Protocol):
    async def create(self, entry: MemoryEntry) -> MemoryEntry: ...
    async def get(self, memory_id: UUID) -> MemoryEntry | None: ...
    async def recall(self, query: MemoryRecall) -> list[MemoryEntry]: ...
    async def forget(self, memory_id: UUID) -> bool: ...


class MemoryNotFoundError(RuntimeError):
    pass


class MemoryService:
    def __init__(self, repository: MemoryRepository) -> None:
        self._repository = repository

    async def remember(self, command: MemoryWrite) -> MemoryEntry:
        entry = MemoryEntry(**command.model_dump())
        return await self._repository.create(entry)

    async def get(self, memory_id: UUID) -> MemoryEntry:
        entry = await self._repository.get(memory_id)
        if entry is None:
            raise MemoryNotFoundError(f"Memory '{memory_id}' not found")
        return entry

    async def recall(self, query: MemoryRecall) -> list[MemoryEntry]:
        return await self._repository.recall(query)

    async def forget(self, memory_id: UUID) -> None:
        if not await self._repository.forget(memory_id):
            raise MemoryNotFoundError(f"Memory '{memory_id}' not found")

    async def capture_execution(
        self,
        *,
        correlation_id: UUID | None,
        agent_key: str,
        skill_key: str | None,
        execution_id: UUID,
        content: str,
        model: str | None,
    ) -> MemoryEntry | None:
        if correlation_id is None or not content.strip():
            return None
        bounded = content.strip()[:12000]
        return await self.remember(
            MemoryWrite(
                scope_type=MemoryScopeType.CORRELATION,
                scope_key=str(correlation_id),
                kind=MemoryKind.EXECUTION_RESULT,
                content=bounded,
                agent_key=agent_key,
                skill_key=skill_key,
                importance=0.6,
                metadata={
                    "execution_id": str(execution_id),
                    "model": model,
                    "captured_by": "agent-runtime",
                    "truncated": len(content.strip()) > len(bounded),
                },
            )
        )
