from __future__ import annotations

from typing import Protocol
from uuid import UUID

from agent_platform.application.observability import MEMORY_ITEMS, MEMORY_RECALLS, timed_span
from agent_platform.domain.memory import MemoryEntry, MemoryKind, MemoryRecall, MemoryScopeType, MemoryWrite


class MemoryRepository(Protocol):
    async def create(self,entry:MemoryEntry)->MemoryEntry:...
    async def get(self,memory_id:UUID)->MemoryEntry|None:...
    async def recall(self,query:MemoryRecall)->list[MemoryEntry]:...
    async def forget(self,memory_id:UUID)->bool:...


class MemoryNotFoundError(RuntimeError):pass


class MemoryService:
    def __init__(self,repository:MemoryRepository)->None:self._repository=repository
    async def remember(self,command):return await self._repository.create(MemoryEntry(**command.model_dump()))
    async def get(self,memory_id):
        entry=await self._repository.get(memory_id)
        if entry is None:raise MemoryNotFoundError(f"Memory '{memory_id}' not found")
        return entry
    async def recall(self,query):
        with timed_span("memory.recall",scope_count=len(query.scopes),limit=query.limit):
            try:
                items=await self._repository.recall(query);MEMORY_RECALLS.labels("ok").inc();MEMORY_ITEMS.observe(len(items));return items
            except Exception:
                MEMORY_RECALLS.labels("error").inc();raise
    async def forget(self,memory_id):
        if not await self._repository.forget(memory_id):raise MemoryNotFoundError(f"Memory '{memory_id}' not found")
    async def capture_execution(self,*,correlation_id,agent_key,skill_key,execution_id,content,model):
        if correlation_id is None or not content.strip():return None
        bounded=content.strip()[:12000]
        return await self.remember(MemoryWrite(scope_type=MemoryScopeType.CORRELATION,scope_key=str(correlation_id),kind=MemoryKind.EXECUTION_RESULT,content=bounded,agent_key=agent_key,skill_key=skill_key,importance=0.6,metadata={"execution_id":str(execution_id),"model":model,"captured_by":"agent-runtime","truncated":len(content.strip())>len(bounded)}))
