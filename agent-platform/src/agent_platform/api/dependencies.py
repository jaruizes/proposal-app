from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.application.cache import CacheService, CachedEmbeddingProvider, InMemoryCacheProvider
from agent_platform.application.cognitive import ApplicationContextContributor, AttachmentContextContributor, CognitiveContextBuilder, KnowledgeRetrievalContributor, MemoryContextContributor
from agent_platform.application.embeddings import EmbeddingProvider
from agent_platform.application.file_ingestion import KnowledgeFileService
from agent_platform.application.ingestion import KnowledgeIngestionService
from agent_platform.application.knowledge import KnowledgeService
from agent_platform.application.memory import MemoryRepository, MemoryService
from agent_platform.application.models import ModelProvider
from agent_platform.application.ontology import OntologyRepository, OntologyService
from agent_platform.application.registries import AgentRegistry, SkillRegistry
from agent_platform.application.repositories import AgentRepository, ExecutionRepository, KnowledgeRepository, SkillRepository
from agent_platform.application.retrieval import KnowledgeRetrievalService
from agent_platform.application.runtime import AgentRuntime
from agent_platform.application.tools import ToolRegistry
from agent_platform.config import get_settings
from agent_platform.persistence.database import get_session
from agent_platform.persistence.memory import PostgresMemoryRepository
from agent_platform.persistence.ontology import PostgresOntologyRepository
from agent_platform.persistence.repositories import PostgresAgentRepository, PostgresExecutionRepository, PostgresKnowledgeRepository, PostgresSkillRepository
from agent_platform.persistence.retrieval import PostgresKnowledgeSearchBackend
from agent_platform.providers import AnthropicModelProvider, HashEmbeddingProvider, McpRegistry, McpServerDefinition, ValkeyCacheProvider

async def get_agent_repository(session:Annotated[AsyncSession,Depends(get_session)])->AgentRepository:return PostgresAgentRepository(session)
async def get_skill_repository(session:Annotated[AsyncSession,Depends(get_session)])->SkillRepository:return PostgresSkillRepository(session)
async def get_execution_repository(session:Annotated[AsyncSession,Depends(get_session)])->ExecutionRepository:return PostgresExecutionRepository(session)
async def get_knowledge_repository(session:Annotated[AsyncSession,Depends(get_session)])->KnowledgeRepository:return PostgresKnowledgeRepository(session)
async def get_memory_repository(session:Annotated[AsyncSession,Depends(get_session)])->MemoryRepository:return PostgresMemoryRepository(session)
async def get_ontology_repository(session:Annotated[AsyncSession,Depends(get_session)])->OntologyRepository:return PostgresOntologyRepository(session)

AgentRepositoryDep=Annotated[AgentRepository,Depends(get_agent_repository)];SkillRepositoryDep=Annotated[SkillRepository,Depends(get_skill_repository)];ExecutionRepositoryDep=Annotated[ExecutionRepository,Depends(get_execution_repository)];KnowledgeRepositoryDep=Annotated[KnowledgeRepository,Depends(get_knowledge_repository)];MemoryRepositoryDep=Annotated[MemoryRepository,Depends(get_memory_repository)];OntologyRepositoryDep=Annotated[OntologyRepository,Depends(get_ontology_repository)]

async def get_skill_registry(repository:SkillRepositoryDep)->SkillRegistry:return SkillRegistry(repository)
async def get_agent_registry(repository:AgentRepositoryDep,skills:SkillRepositoryDep)->AgentRegistry:return AgentRegistry(repository,skills)
async def get_knowledge_service(repository:KnowledgeRepositoryDep)->KnowledgeService:return KnowledgeService(repository)
async def get_memory_service(repository:MemoryRepositoryDep)->MemoryService:return MemoryService(repository)
SkillRegistryDep=Annotated[SkillRegistry,Depends(get_skill_registry)];AgentRegistryDep=Annotated[AgentRegistry,Depends(get_agent_registry)];KnowledgeServiceDep=Annotated[KnowledgeService,Depends(get_knowledge_service)];MemoryServiceDep=Annotated[MemoryService,Depends(get_memory_service)]

@lru_cache
def get_cache_service()->CacheService:
    settings=get_settings();provider=ValkeyCacheProvider(settings.cache_url) if settings.cache_backend.lower() in {"valkey","redis"} else InMemoryCacheProvider();return CacheService(provider,prefix=settings.cache_prefix)
CacheServiceDep=Annotated[CacheService,Depends(get_cache_service)]

async def get_ontology_service(repository:OntologyRepositoryDep,knowledge:KnowledgeRepositoryDep,cache:CacheServiceDep)->OntologyService:return OntologyService(repository,knowledge,cache)
OntologyServiceDep=Annotated[OntologyService,Depends(get_ontology_service)]

def get_model_provider()->ModelProvider:return AnthropicModelProvider()
ModelProviderDep=Annotated[ModelProvider,Depends(get_model_provider)]

@lru_cache
def get_embedding_provider()->EmbeddingProvider:
    settings=get_settings();base=HashEmbeddingProvider(dimensions=settings.embedding_dimensions,model=settings.embedding_model);return CachedEmbeddingProvider(base,get_cache_service(),ttl_seconds=settings.embedding_cache_ttl_seconds)
EmbeddingProviderDep=Annotated[EmbeddingProvider,Depends(get_embedding_provider)]

async def get_knowledge_ingestion_service(repository:KnowledgeRepositoryDep,embedding_provider:EmbeddingProviderDep,cache:CacheServiceDep,ontology:OntologyServiceDep)->KnowledgeIngestionService:return KnowledgeIngestionService(repository,embedding_provider,cache=cache,ontology_service=ontology)
KnowledgeIngestionServiceDep=Annotated[KnowledgeIngestionService,Depends(get_knowledge_ingestion_service)]

async def get_knowledge_file_service(knowledge_service:KnowledgeServiceDep,ingestion_service:KnowledgeIngestionServiceDep)->KnowledgeFileService:return KnowledgeFileService(knowledge_service,ingestion_service)
KnowledgeFileServiceDep=Annotated[KnowledgeFileService,Depends(get_knowledge_file_service)]

async def get_knowledge_retrieval_service(session:Annotated[AsyncSession,Depends(get_session)],embedding_provider:EmbeddingProviderDep,cache:CacheServiceDep,ontology:OntologyServiceDep)->KnowledgeRetrievalService:
    settings=get_settings();return KnowledgeRetrievalService(PostgresKnowledgeSearchBackend(session),embedding_provider,cache,ontology,cache_ttl_seconds=settings.retrieval_cache_ttl_seconds)
KnowledgeRetrievalServiceDep=Annotated[KnowledgeRetrievalService,Depends(get_knowledge_retrieval_service)]

async def get_cognitive_context_builder(retrieval_service:KnowledgeRetrievalServiceDep,memory_service:MemoryServiceDep,cache:CacheServiceDep)->CognitiveContextBuilder:
    settings=get_settings();return CognitiveContextBuilder(contributors=[ApplicationContextContributor(),AttachmentContextContributor(),MemoryContextContributor(memory_service),KnowledgeRetrievalContributor(retrieval_service,cache,cache_ttl_seconds=settings.cognitive_cache_ttl_seconds)])
CognitiveContextBuilderDep=Annotated[CognitiveContextBuilder,Depends(get_cognitive_context_builder)]

def get_agent_runtime(agents:AgentRegistryDep,skills:SkillRegistryDep,executions:ExecutionRepositoryDep,model_provider:ModelProviderDep,cognitive_context_builder:CognitiveContextBuilderDep,memory_service:MemoryServiceDep,cache:CacheServiceDep)->AgentRuntime:return AgentRuntime(agents,skills,executions,model_provider,cognitive_context_builder=cognitive_context_builder,memory_service=memory_service,cache=cache)
AgentRuntimeDep=Annotated[AgentRuntime,Depends(get_agent_runtime)]

@lru_cache
def get_mcp_registry()->McpRegistry:
    settings=get_settings();registry=McpRegistry()
    if settings.google_workspace_mcp_enabled:
        env={}
        if settings.google_oauth_credentials:env["GOOGLE_OAUTH_CREDENTIALS"]=settings.google_oauth_credentials
        if settings.google_oauth_token:env["GOOGLE_OAUTH_TOKEN"]=settings.google_oauth_token
        registry.register(McpServerDefinition(key="google-workspace",command=settings.google_workspace_mcp_command,args=(settings.google_workspace_mcp_script,),cwd=settings.google_workspace_mcp_cwd,env=env,timeout_seconds=settings.google_workspace_mcp_timeout_seconds))
    return registry

@lru_cache
def get_tool_registry()->ToolRegistry:return ToolRegistry(get_mcp_registry().tool_providers())
McpRegistryDep=Annotated[McpRegistry,Depends(get_mcp_registry)];ToolRegistryDep=Annotated[ToolRegistry,Depends(get_tool_registry)]
