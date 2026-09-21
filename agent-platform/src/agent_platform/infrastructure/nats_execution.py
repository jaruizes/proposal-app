from __future__ import annotations

import asyncio
import json
from typing import Any

import nats
from nats.errors import TimeoutError as NatsTimeoutError
from nats.js.errors import NotFoundError

from agent_platform.api.dependencies import get_cache_service,get_tool_registry
from agent_platform.application.cache import CachedEmbeddingProvider
from agent_platform.application.cognitive import ApplicationContextContributor,AttachmentContextContributor,CognitiveContextBuilder,KnowledgeRetrievalContributor,MemoryContextContributor
from agent_platform.application.langgraph_runtime import LangGraphAgentRuntime
from agent_platform.application.memory import MemoryService
from agent_platform.application.ontology import OntologyService
from agent_platform.application.registries import AgentRegistry,SkillRegistry
from agent_platform.application.retrieval import KnowledgeRetrievalService
from agent_platform.application.runtime import AgentRuntime
from agent_platform.config import get_settings
from agent_platform.domain import AgentExecutionCommandEnvelope,AgentExecutionEventEnvelope,AgentExecutionRequest,ExecutionStatus
from agent_platform.persistence.database import SessionFactory
from agent_platform.persistence.memory import PostgresMemoryRepository
from agent_platform.persistence.ontology import PostgresOntologyRepository
from agent_platform.persistence.repositories import PostgresAgentRepository,PostgresExecutionRepository,PostgresKnowledgeRepository,PostgresSkillRepository
from agent_platform.persistence.retrieval import PostgresKnowledgeSearchBackend
from agent_platform.providers import AnthropicModelProvider,HashEmbeddingProvider


class NatsExecutionEventPublisher:
    def __init__(self, jetstream) -> None:self._js=jetstream

    async def publish(self, execution_id, event_type:str, payload:dict[str,Any]) -> None:
        subject_event="progressed"
        if event_type=="execution.running":subject_event="started"
        elif event_type=="execution.result":subject_event="completed"
        elif event_type=="execution.failed":subject_event="failed"
        envelope=AgentExecutionEventEnvelope(
            schema_version="1",
            message_type="agent.execution.event",
            execution_id=execution_id,
            event_type=f"execution.{subject_event}",
            source_event_type=event_type,
            payload=payload,
        )
        message_id=f"{execution_id}:{event_type}:{payload.get('provider_request_id') or payload.get('status') or ''}"
        await self._js.publish(
            f"agent-platform.events.execution.{subject_event}",
            json.dumps(envelope.model_dump(mode="json"),separators=(",",":"),default=str).encode(),
            headers={"Nats-Msg-Id":message_id},
        )


class EventPublishingExecutionRepository:
    def __init__(self,delegate,publisher):self._delegate=delegate;self._publisher=publisher
    async def get(self,*a,**k):return await self._delegate.get(*a,**k)
    async def create(self,*a,**k):return await self._delegate.create(*a,**k)
    async def update(self,*a,**k):return await self._delegate.update(*a,**k)
    async def list_events(self,*a,**k):return await self._delegate.list_events(*a,**k)
    async def add_event(self,execution_id,event_type,payload):
        await self._delegate.add_event(execution_id,event_type,payload)
        await self._publisher.publish(execution_id,event_type,payload)


class NatsExecutionTransport:
    def __init__(self)->None:self._nc=None;self._js=None;self._subscription=None;self._task=None;self._publisher=None

    async def start(self)->None:
        settings=get_settings()
        if not settings.nats_enabled:return
        self._nc=await nats.connect(settings.nats_url,name="proposal-agent-platform")
        self._js=self._nc.jetstream()
        await self._ensure_stream(settings.nats_commands_stream,[settings.nats_command_subject])
        await self._ensure_stream(settings.nats_events_stream,[settings.nats_events_subject])
        self._publisher=NatsExecutionEventPublisher(self._js)
        self._subscription=await self._js.pull_subscribe(settings.nats_command_subject,durable=settings.nats_command_durable,stream=settings.nats_commands_stream)
        self._task=asyncio.create_task(self._consume(),name="nats-execution-consumer")

    async def stop(self)->None:
        if self._task:
            self._task.cancel()
            try:await self._task
            except asyncio.CancelledError:pass
        if self._nc:await self._nc.drain()

    async def _ensure_stream(self,name,subjects):
        try:await self._js.stream_info(name)
        except NotFoundError:await self._js.add_stream(name=name,subjects=subjects)

    async def _consume(self):
        while True:
            try:
                messages=await self._subscription.fetch(1,timeout=1)
            except (NatsTimeoutError,asyncio.TimeoutError):
                continue
            for message in messages:
                stop=asyncio.Event();heartbeat=asyncio.create_task(self._heartbeat(message,stop))
                try:
                    envelope=AgentExecutionCommandEnvelope.model_validate_json(message.data)
                    request=envelope.request.model_copy(update={"execution_id":envelope.execution_id})
                    await self._execute(request)
                    await message.ack()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    if self._publisher is not None:
                        execution_id=getattr(envelope,"execution_id",None) if "envelope" in locals() else None
                        if execution_id is not None:
                            await self._publisher.publish(execution_id,"execution.failed",{"status":"FAILED","error":{"code":"NATS_COMMAND_ERROR","message":str(exc),"retryable":True}})
                    await message.nak()
                finally:
                    stop.set();heartbeat.cancel()
                    try:await heartbeat
                    except asyncio.CancelledError:pass

    async def _heartbeat(self,message,stop):
        while not stop.is_set():
            await asyncio.sleep(20)
            if not stop.is_set():
                try:await message.in_progress()
                except Exception:return

    async def _execute(self,request):
        settings=get_settings();cache=get_cache_service();tools=get_tool_registry()
        async with SessionFactory() as session:
            agent_repo=PostgresAgentRepository(session);skill_repo=PostgresSkillRepository(session)
            base_execution_repo=PostgresExecutionRepository(session)
            execution_repo=EventPublishingExecutionRepository(base_execution_repo,self._publisher)
            knowledge_repo=PostgresKnowledgeRepository(session)
            existing=await execution_repo.get(request.execution_id) if request.execution_id else None
            if existing and existing.status in {ExecutionStatus.COMPLETED,ExecutionStatus.FAILED,ExecutionStatus.CANCELLED}:
                events=await execution_repo.list_events(existing.id)
                terminal=next((e for e in reversed(events) if e["event_type"] in {"execution.result","execution.failed"}),None)
                if terminal:await self._publisher.publish(existing.id,terminal["event_type"],terminal["payload"])
                return
            memory=MemoryService(PostgresMemoryRepository(session))
            ontology=OntologyService(PostgresOntologyRepository(session),knowledge_repo,cache)
            embeddings=CachedEmbeddingProvider(HashEmbeddingProvider(dimensions=settings.embedding_dimensions,model=settings.embedding_model),cache,ttl_seconds=settings.embedding_cache_ttl_seconds)
            retrieval=KnowledgeRetrievalService(PostgresKnowledgeSearchBackend(session),embeddings,cache,ontology,cache_ttl_seconds=settings.retrieval_cache_ttl_seconds)
            context=CognitiveContextBuilder(contributors=[ApplicationContextContributor(),AttachmentContextContributor(),MemoryContextContributor(memory),KnowledgeRetrievalContributor(retrieval,cache,cache_ttl_seconds=settings.cognitive_cache_ttl_seconds)])
            common=dict(agents=AgentRegistry(agent_repo,skill_repo),skills=SkillRegistry(skill_repo),executions=execution_repo,model_provider=AnthropicModelProvider(),cognitive_context_builder=context,memory_service=memory,cache=cache,tool_registry=tools)
            if settings.agent_runtime.lower()=="langgraph":
                runtime=LangGraphAgentRuntime(**common,checkpoint_database_url=settings.langgraph_checkpoint_database_url,proposal_retrieval_service=retrieval)
            else:
                runtime=AgentRuntime(**common)
            if existing is None:await runtime.execute(request)
            else:await runtime.run(existing,request)


_transport=NatsExecutionTransport()
def get_nats_execution_transport()->NatsExecutionTransport:return _transport
