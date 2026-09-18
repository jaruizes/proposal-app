from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from prometheus_client import make_asgi_app
from pydantic import BaseModel

from agent_platform.api.admin import router as admin_router
from agent_platform.api.agents import router as agents_router
from agent_platform.api.cache import router as cache_router
from agent_platform.api.executions import router as executions_router
from agent_platform.api.knowledge import router as knowledge_router
from agent_platform.api.memory import router as memory_router
from agent_platform.api.ontology import router as ontology_router
from agent_platform.api.retrieval import router as retrieval_router
from agent_platform.api.skills import router as skills_router
from agent_platform.api.tools import router as tools_router
from agent_platform.application.observability import configure_observability
from agent_platform.config import get_settings

settings=get_settings()
configure_observability(service_name=settings.otel_service_name,enabled=settings.observability_enabled,otlp_endpoint=settings.otel_exporter_otlp_endpoint)

class HealthResponse(BaseModel):
    status:str;service:str;version:str

app=FastAPI(title="Proposal Agent Platform",version="0.1.0",description="Independent runtime and API for configurable agents, skills and cognitive services.")
app.include_router(agents_router);app.include_router(skills_router);app.include_router(executions_router);app.include_router(tools_router);app.include_router(knowledge_router);app.include_router(retrieval_router);app.include_router(memory_router);app.include_router(cache_router);app.include_router(ontology_router);app.include_router(admin_router)
app.mount("/metrics",make_asgi_app())
app.mount("/admin",StaticFiles(directory=str(Path(__file__).resolve().parent/"admin_ui"),html=True),name="admin")

@app.get("/health",response_model=HealthResponse,tags=["platform"])
async def health()->HealthResponse:return HealthResponse(status="ok",service="proposal-agent-platform",version=app.version)
