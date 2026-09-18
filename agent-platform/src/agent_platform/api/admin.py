from fastapi import APIRouter

from agent_platform.api.dependencies import (
    AgentRegistryDep,
    CacheServiceDep,
    KnowledgeServiceDep,
    McpRegistryDep,
    OntologyServiceDep,
    SkillRegistryDep,
)
from agent_platform.config import get_settings

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.get("/overview")
async def overview(
    agents: AgentRegistryDep,
    skills: SkillRegistryDep,
    knowledge: KnowledgeServiceDep,
    ontology: OntologyServiceDep,
    cache: CacheServiceDep,
    mcp: McpRegistryDep,
) -> dict:
    agent_items = await agents.list()
    skill_items = await skills.list()
    bases = await knowledge.list_bases()
    concepts = await ontology.list_concepts()
    relationships = await ontology.list_relationships()
    return {
        "counts": {
            "agents": len(agent_items),
            "skills": len(skill_items),
            "knowledge_bases": len(bases),
            "ontology_concepts": len(concepts),
            "ontology_relationships": len(relationships),
            "mcp_servers": len(mcp.list_servers()),
        },
        "cache": cache.stats(),
    }


@router.get("/config")
async def config() -> dict:
    settings = get_settings()
    return {
        "service": settings.otel_service_name,
        "embedding": {
            "provider": settings.embedding_provider,
            "model": settings.embedding_model,
            "dimensions": settings.embedding_dimensions,
        },
        "cache": {
            "backend": settings.cache_backend,
            "embedding_ttl_seconds": settings.embedding_cache_ttl_seconds,
            "retrieval_ttl_seconds": settings.retrieval_cache_ttl_seconds,
            "cognitive_ttl_seconds": settings.cognitive_cache_ttl_seconds,
        },
        "observability": {
            "enabled": settings.observability_enabled,
            "otlp_endpoint": settings.otel_exporter_otlp_endpoint,
            "metrics_path": "/metrics",
            "jaeger_url": "http://localhost:16686",
        },
        "mcp": {
            "google_workspace_enabled": settings.google_workspace_mcp_enabled,
        },
    }
