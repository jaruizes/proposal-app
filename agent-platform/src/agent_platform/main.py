from fastapi import FastAPI
from pydantic import BaseModel
from agent_platform.api.agents import router as agents_router
from agent_platform.api.cache import router as cache_router
from agent_platform.api.executions import router as executions_router
from agent_platform.api.knowledge import router as knowledge_router
from agent_platform.api.memory import router as memory_router
from agent_platform.api.retrieval import router as retrieval_router
from agent_platform.api.skills import router as skills_router
from agent_platform.api.tools import router as tools_router

class HealthResponse(BaseModel):
    status:str; service:str; version:str

app=FastAPI(title="Proposal Agent Platform",version="0.1.0",description="Independent runtime and API for configurable agents, skills and cognitive services.")
app.include_router(agents_router);app.include_router(skills_router);app.include_router(executions_router);app.include_router(tools_router);app.include_router(knowledge_router);app.include_router(retrieval_router);app.include_router(memory_router);app.include_router(cache_router)

@app.get("/health",response_model=HealthResponse,tags=["platform"])
async def health()->HealthResponse:return HealthResponse(status="ok",service="proposal-agent-platform",version=app.version)
