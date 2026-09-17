from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.domain import (
    AgentConstraints,
    AgentDefinition,
    AgentError,
    AgentExecution,
    AgentUsage,
    ExecutionStatus,
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentStatus,
    ModelPolicy,
    SkillDefinition,
)
from agent_platform.persistence.models import (
    AgentCapabilityRecord,
    AgentKnowledgeScopeRecord,
    AgentRecord,
    AgentSkillRecord,
    AgentToolRecord,
    ExecutionEventRecord,
    ExecutionRecord,
    KnowledgeBaseRecord,
    KnowledgeChunkRecord,
    KnowledgeDocumentRecord,
    SkillRecord,
)


def _agent_to_domain(record: AgentRecord) -> AgentDefinition:
    return AgentDefinition(id=record.id,key=record.key,name=record.name,description=record.description,role=record.role,capabilities=[item.value for item in record.capabilities],skills=[item.skill_key for item in record.skills],knowledge_scopes=[item.scope_key for item in record.knowledge_scopes],allowed_tools=[item.tool_key for item in record.tools],model_policy=ModelPolicy.model_validate(record.model_policy or {}),constraints=AgentConstraints.model_validate(record.constraints or {}),version=record.version,enabled=record.enabled)

def _skill_to_domain(record: SkillRecord) -> SkillDefinition:
    return SkillDefinition(id=record.id,key=record.key,name=record.name,description=record.description,objective=record.objective,instructions=record.instructions,inputs=record.inputs or [],output_schema=record.output_schema or {},knowledge_sources=record.knowledge_sources or [],allowed_tools=record.allowed_tools or [],constraints=record.constraints or {},version=record.version,enabled=record.enabled)

def _execution_to_domain(record: ExecutionRecord) -> AgentExecution:
    return AgentExecution(id=record.id,correlation_id=record.correlation_id,agent_key=record.agent_key,skill_key=record.skill_key,status=ExecutionStatus(record.status),objective=record.objective,runtime=record.runtime,model=record.model,started_at=record.started_at,completed_at=record.completed_at,created_at=record.created_at,usage=AgentUsage.model_validate(record.usage or {}),provider_request_id=record.provider_request_id,trace_id=record.trace_id,error=AgentError.model_validate(record.error) if record.error else None)

def _base_to_domain(record: KnowledgeBaseRecord) -> KnowledgeBase:
    return KnowledgeBase(id=record.id,key=record.key,name=record.name,description=record.description,metadata=record.metadata_json or {},enabled=record.enabled,created_at=record.created_at)

def _document_to_domain(record: KnowledgeDocumentRecord) -> KnowledgeDocument:
    return KnowledgeDocument(id=record.id,knowledge_base_key=record.knowledge_base_key,title=record.title,content=record.content,media_type=record.media_type,source_uri=record.source_uri,metadata=record.metadata_json or {},status=KnowledgeDocumentStatus(record.status),created_at=record.created_at)

def _chunk_to_domain(record: KnowledgeChunkRecord) -> KnowledgeChunk:
    return KnowledgeChunk(id=record.id,document_id=record.document_id,ordinal=record.ordinal,content=record.content,metadata=record.metadata_json or {},created_at=record.created_at)


class PostgresAgentRepository:
    def __init__(self, session: AsyncSession) -> None: self.session = session
    async def list(self):
        result = await self.session.execute(select(AgentRecord).order_by(AgentRecord.key)); return [_agent_to_domain(r) for r in result.scalars().unique().all()]
    async def get_by_key(self,key):
        result=await self.session.execute(select(AgentRecord).where(AgentRecord.key==key)); r=result.scalars().unique().one_or_none(); return _agent_to_domain(r) if r else None
    async def create(self,agent):
        self.session.add(AgentRecord(id=agent.id,key=agent.key,name=agent.name,description=agent.description,role=agent.role,model_policy=agent.model_policy.model_dump(mode="json"),constraints=agent.constraints.model_dump(mode="json"),version=agent.version,enabled=agent.enabled,capabilities=[AgentCapabilityRecord(value=v) for v in agent.capabilities],skills=[AgentSkillRecord(skill_key=v) for v in agent.skills],tools=[AgentToolRecord(tool_key=v) for v in agent.allowed_tools],knowledge_scopes=[AgentKnowledgeScopeRecord(scope_key=v) for v in agent.knowledge_scopes])); await self.session.commit(); return agent
    async def update(self,agent):
        result=await self.session.execute(select(AgentRecord).where(AgentRecord.key==agent.key)); r=result.scalars().unique().one(); r.name=agent.name; r.description=agent.description; r.role=agent.role; r.model_policy=agent.model_policy.model_dump(mode="json"); r.constraints=agent.constraints.model_dump(mode="json"); r.version=agent.version; r.enabled=agent.enabled; r.capabilities=[AgentCapabilityRecord(value=v) for v in agent.capabilities]; r.skills=[AgentSkillRecord(skill_key=v) for v in agent.skills]; r.tools=[AgentToolRecord(tool_key=v) for v in agent.allowed_tools]; r.knowledge_scopes=[AgentKnowledgeScopeRecord(scope_key=v) for v in agent.knowledge_scopes]; await self.session.commit(); return agent

class PostgresSkillRepository:
    def __init__(self, session: AsyncSession) -> None: self.session=session
    async def list(self):
        result=await self.session.execute(select(SkillRecord).order_by(SkillRecord.key)); return [_skill_to_domain(r) for r in result.scalars().all()]
    async def get_by_key(self,key):
        result=await self.session.execute(select(SkillRecord).where(SkillRecord.key==key)); r=result.scalar_one_or_none(); return _skill_to_domain(r) if r else None
    async def create(self,skill):
        self.session.add(SkillRecord(id=skill.id,key=skill.key,name=skill.name,description=skill.description,objective=skill.objective,instructions=skill.instructions,inputs=skill.inputs,output_schema=skill.output_schema,knowledge_sources=skill.knowledge_sources,allowed_tools=skill.allowed_tools,constraints=skill.constraints,version=skill.version,enabled=skill.enabled)); await self.session.commit(); return skill
    async def update(self,skill):
        result=await self.session.execute(select(SkillRecord).where(SkillRecord.key==skill.key)); r=result.scalar_one(); r.name=skill.name; r.description=skill.description; r.objective=skill.objective; r.instructions=skill.instructions; r.inputs=skill.inputs; r.output_schema=skill.output_schema; r.knowledge_sources=skill.knowledge_sources; r.allowed_tools=skill.allowed_tools; r.constraints=skill.constraints; r.version=skill.version; r.enabled=skill.enabled; await self.session.commit(); return skill

class PostgresExecutionRepository:
    def __init__(self, session: AsyncSession) -> None: self.session=session
    async def get(self,execution_id):
        r=await self.session.get(ExecutionRecord,execution_id); return _execution_to_domain(r) if r else None
    async def create(self,e):
        self.session.add(ExecutionRecord(id=e.id,correlation_id=e.correlation_id,agent_key=e.agent_key,skill_key=e.skill_key,status=e.status.value,objective=e.objective,runtime=e.runtime,model=e.model,started_at=e.started_at,completed_at=e.completed_at,created_at=e.created_at,usage=e.usage.model_dump(mode="json"),provider_request_id=e.provider_request_id,trace_id=e.trace_id,error=e.error.model_dump(mode="json") if e.error else None)); await self.session.commit(); return e
    async def update(self,e):
        r=await self.session.get(ExecutionRecord,e.id)
        if r is None: raise LookupError(f"Execution '{e.id}' not found")
        r.status=e.status.value; r.runtime=e.runtime; r.model=e.model; r.started_at=e.started_at; r.completed_at=e.completed_at; r.usage=e.usage.model_dump(mode="json"); r.provider_request_id=e.provider_request_id; r.trace_id=e.trace_id; r.error=e.error.model_dump(mode="json") if e.error else None; await self.session.commit(); return e
    async def add_event(self,execution_id,event_type,payload):
        self.session.add(ExecutionEventRecord(execution_id=execution_id,event_type=event_type,payload=payload,created_at=datetime.now(timezone.utc))); await self.session.commit()
    async def list_events(self,execution_id):
        result=await self.session.execute(select(ExecutionEventRecord).where(ExecutionEventRecord.execution_id==execution_id).order_by(ExecutionEventRecord.created_at)); return [{"event_type":r.event_type,"payload":r.payload,"created_at":r.created_at.isoformat()} for r in result.scalars().all()]

class PostgresKnowledgeRepository:
    def __init__(self, session: AsyncSession) -> None: self.session=session
    async def list_bases(self):
        result=await self.session.execute(select(KnowledgeBaseRecord).order_by(KnowledgeBaseRecord.key)); return [_base_to_domain(r) for r in result.scalars().all()]
    async def get_base(self,key):
        result=await self.session.execute(select(KnowledgeBaseRecord).where(KnowledgeBaseRecord.key==key)); r=result.scalar_one_or_none(); return _base_to_domain(r) if r else None
    async def create_base(self,item):
        self.session.add(KnowledgeBaseRecord(id=item.id,key=item.key,name=item.name,description=item.description,metadata_json=item.metadata,enabled=item.enabled,created_at=item.created_at)); await self.session.commit(); return item
    async def create_document(self,item):
        self.session.add(KnowledgeDocumentRecord(id=item.id,knowledge_base_key=item.knowledge_base_key,title=item.title,content=item.content,media_type=item.media_type,source_uri=item.source_uri,metadata_json=item.metadata,status=item.status.value,created_at=item.created_at)); await self.session.commit(); return item
    async def list_documents(self,key):
        result=await self.session.execute(select(KnowledgeDocumentRecord).where(KnowledgeDocumentRecord.knowledge_base_key==key).order_by(KnowledgeDocumentRecord.created_at)); return [_document_to_domain(r) for r in result.scalars().all()]
    async def get_document(self,document_id):
        r=await self.session.get(KnowledgeDocumentRecord,document_id); return _document_to_domain(r) if r else None
    async def create_chunks(self,chunks):
        self.session.add_all([KnowledgeChunkRecord(id=c.id,document_id=c.document_id,ordinal=c.ordinal,content=c.content,metadata_json=c.metadata,created_at=c.created_at) for c in chunks]); await self.session.commit(); return chunks
    async def list_chunks(self,document_id):
        result=await self.session.execute(select(KnowledgeChunkRecord).where(KnowledgeChunkRecord.document_id==document_id).order_by(KnowledgeChunkRecord.ordinal)); return [_chunk_to_domain(r) for r in result.scalars().all()]
