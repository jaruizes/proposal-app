from fastapi import APIRouter, HTTPException

from agent_platform.api.dependencies import KnowledgeRetrievalServiceDep
from agent_platform.application.retrieval import KnowledgeRetrievalError
from agent_platform.domain.retrieval import RetrievalQuery, RetrievalResult


router = APIRouter(prefix="/v1/knowledge", tags=["knowledge-retrieval"])


@router.post("/retrieve", response_model=RetrievalResult)
async def retrieve(payload: RetrievalQuery, service: KnowledgeRetrievalServiceDep) -> RetrievalResult:
    try:
        return await service.retrieve(payload)
    except KnowledgeRetrievalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
