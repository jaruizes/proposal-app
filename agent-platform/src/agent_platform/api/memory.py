from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from agent_platform.api.dependencies import MemoryServiceDep
from agent_platform.application.memory import MemoryNotFoundError
from agent_platform.domain.memory import MemoryEntry, MemoryRecall, MemoryWrite


router = APIRouter(prefix="/v1/memory", tags=["memory"])


@router.post("", response_model=MemoryEntry, status_code=status.HTTP_201_CREATED)
async def remember(payload: MemoryWrite, service: MemoryServiceDep) -> MemoryEntry:
    return await service.remember(payload)


@router.post("/recall", response_model=list[MemoryEntry])
async def recall(payload: MemoryRecall, service: MemoryServiceDep) -> list[MemoryEntry]:
    return await service.recall(payload)


@router.get("/{memory_id}", response_model=MemoryEntry)
async def get_memory(memory_id: UUID, service: MemoryServiceDep) -> MemoryEntry:
    try:
        return await service.get(memory_id)
    except MemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def forget(memory_id: UUID, service: MemoryServiceDep) -> Response:
    try:
        await service.forget(memory_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except MemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
