from __future__ import annotations
import asyncio

from agent_platform.application.cache import CachedEmbeddingProvider
from agent_platform.application.cognitive import ApplicationContextContributor,AttachmentContextContributor,CognitiveContextBuilder,KnowledgeRetrievalContributor,MemoryContextContributor
from agent_platform.application.langgraph_runtime import LangGraphAgentRuntime
from agent_platform.application.memory import MemoryService
from agent_platform.application.ontology import OntologyService
from agent_platform.application.registries import AgentRegistry,SkillRegistry
from agent_platform.application.retrieval import KnowledgeRetrievalService
from agent_platform.application.runtime import AgentRuntime
from agent_platform.config import get_settings
from agent_platform.persistence.database import SessionFactory
from agent_platform.persistence.memory import PostgresMemoryRepository
from agent_platform.persistence.ontology import PostgresOntologyRepository
from agent_platform.persistence.repositories import PostgresAgentRepository,PostgresExecutionRepository,PostgresKnowledgeRepository,PostgresSkillRepository
from agent_platform.persistence.retrieval import PostgresKnowledgeSearchBackend
from agent_platform.providers import AnthropicModelProvider,HashEmbeddingProvider
from agent_platform.api.dependencies import get_cache_service

class ExecutionDispatcher:
    def __init__(self):self._tasks=set()
    def dispatch(self,execution_id,request):
        task=asyncio.create_task(self._run(execution_id,request),name=f"execution-{execution_id}")
        self._tasks.add(task);task.add_done_callback(self._tasks.discard)
    async def _run(self,execution_id,request):
        settings=get_settings();cache=get_cache_service()
        async with SessionFactory() as session:
            agent_repo=PostgresAgentRepository(session);skill_repo=PostgresSkillRepository(session);execution_repo=PostgresExecutionRepository(session);knowledge_repo=PostgresKnowledgeRepository(session)
            memory=MemoryService(PostgresMemoryRepository(session));ontology=OntologyService(PostgresOntologyRepository(session),knowledge_repo,cache)
            embeddings=CachedEmbeddingProvider(HashEmbeddingProvider(dimensions=settings.embedding_dimensions,model=settings.embedding_model),cache,ttl_seconds=settings.embedding_cache_ttl_seconds)
            retrieval=KnowledgeRetrievalService(PostgresKnowledgeSearchBackend(session),embeddings,cache,ontology,cache_ttl_seconds=settings.retrieval_cache_ttl_seconds)
            context=CognitiveContextBuilder(contributors=[ApplicationContextContributor(),AttachmentContextContributor(),MemoryContextContributor(memory),KnowledgeRetrievalContributor(retrieval,cache,cache_ttl_seconds=settings.cognitive_cache_ttl_seconds)])
            common=dict(
                agents=AgentRegistry(agent_repo,skill_repo),
                skills=SkillRegistry(skill_repo),
                executions=execution_repo,
                model_provider=AnthropicModelProvider(),
                cognitive_context_builder=context,
                memory_service=memory,
                cache=cache,
            )
            if settings.agent_runtime.lower()=="langgraph":
                runtime=LangGraphAgentRuntime(**common,checkpoint_database_url=settings.langgraph_checkpoint_database_url,proposal_retrieval_service=retrieval)
            else:
                runtime=AgentRuntime(**common)
            execution=await execution_repo.get(execution_id)
            if execution is not None:await runtime.run(execution,request)

_dispatcher=ExecutionDispatcher()
def get_execution_dispatcher():return _dispatcher
