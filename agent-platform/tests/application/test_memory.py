from uuid import uuid4

import pytest

from agent_platform.application.cognitive import CognitiveContextBuilder, MemoryContextContributor
from agent_platform.application.memory import MemoryService
from agent_platform.domain import AgentDefinition, AgentExecutionRequest, CognitiveSection, EpistemicLabel, MemoryKind, MemoryRecall, MemoryScope, MemoryScopeType, MemoryWrite, SkillDefinition


class Repo:
    def __init__(self): self.items={}
    async def create(self,entry): self.items[entry.id]=entry; return entry
    async def get(self,memory_id): return self.items.get(memory_id)
    async def recall(self,query):
        pairs={(s.type,s.key) for s in query.scopes}; values=[m for m in self.items.values() if m.active and (m.scope_type,m.scope_key) in pairs]
        if query.kinds: values=[m for m in values if m.kind in query.kinds]
        return sorted(values,key=lambda m:(-m.importance,-m.created_at.timestamp()))[:query.limit]
    async def forget(self,memory_id):
        if memory_id not in self.items: return False
        self.items[memory_id]=self.items[memory_id].model_copy(update={"active":False}); return True


def agent(): return AgentDefinition(key="business-analyst",name="BA",role="Analyze",skills=["analyze-opportunity"])
def skill(**overrides):
    data={"key":"analyze-opportunity","name":"Analyze","objective":"Analyze","instructions":"Analyze evidence"}; data.update(overrides); return SkillDefinition(**data)


@pytest.mark.asyncio
async def test_remember_recall_and_forget():
    repo=Repo(); service=MemoryService(repo); correlation=str(uuid4())
    entry=await service.remember(MemoryWrite(scope_type=MemoryScopeType.CORRELATION,scope_key=correlation,kind=MemoryKind.DECISION,content="Use AWS",importance=0.9))
    recalled=await service.recall(MemoryRecall(scopes=[MemoryScope(type=MemoryScopeType.CORRELATION,key=correlation)]))
    assert recalled[0].id==entry.id
    await service.forget(entry.id)
    assert await service.recall(MemoryRecall(scopes=[MemoryScope(type=MemoryScopeType.CORRELATION,key=correlation)])) == []


@pytest.mark.asyncio
async def test_memory_flows_into_cognitive_context_with_epistemic_label():
    repo=Repo(); service=MemoryService(repo); correlation=uuid4()
    await service.remember(MemoryWrite(scope_type=MemoryScopeType.CORRELATION,scope_key=str(correlation),kind=MemoryKind.DECISION,content="Customer approved phased migration",importance=0.95))
    builder=CognitiveContextBuilder(contributors=[MemoryContextContributor(service)])
    context=await builder.build(agent(),skill(),AgentExecutionRequest(correlation_id=correlation,agent_key="business-analyst",skill_key="analyze-opportunity",objective="Continue analysis"))
    items=context.by_section(CognitiveSection.MEMORY)
    assert len(items)==1
    assert items[0].label is EpistemicLabel.DECISION
    assert "phased migration" in items[0].content["content"]


@pytest.mark.asyncio
async def test_agent_scope_is_opt_in():
    repo=Repo(); service=MemoryService(repo)
    await service.remember(MemoryWrite(scope_type=MemoryScopeType.AGENT,scope_key="business-analyst",content="Reusable agent observation"))
    contributor=MemoryContextContributor(service); request=AgentExecutionRequest(agent_key="business-analyst",skill_key="analyze-opportunity",objective="Analyze")
    assert await contributor.contribute(agent(),skill(),request)==[]
    configured=skill(constraints={"memory":{"include_agent_scope":True}})
    assert len(await contributor.contribute(agent(),configured,request))==1


@pytest.mark.asyncio
async def test_capture_execution_creates_correlation_memory():
    repo=Repo(); service=MemoryService(repo); correlation=uuid4(); execution=uuid4()
    created=await service.capture_execution(correlation_id=correlation,agent_key="business-analyst",skill_key="analyze-opportunity",execution_id=execution,content="Analysis result",model="claude-test")
    assert created is not None
    assert created.kind is MemoryKind.EXECUTION_RESULT
    assert created.scope_key==str(correlation)
    assert created.metadata["execution_id"]==str(execution)
