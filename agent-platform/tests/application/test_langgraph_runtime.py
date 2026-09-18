from datetime import datetime, timezone
from uuid import UUID

import pytest
from langgraph.checkpoint.memory import MemorySaver

from agent_platform.application.langgraph_runtime import LangGraphAgentRuntime
from agent_platform.application.models import ModelRequest, ModelResult, ModelUsage
from agent_platform.application.registries import AgentRegistry, SkillRegistry
from agent_platform.domain import AgentDefinition, AgentExecution, AgentExecutionRequest, ExecutionStatus, SkillDefinition


class AgentRepo:
    def __init__(self,item):self.item=item
    async def list(self):return[self.item]
    async def get_by_key(self,key):return self.item if key==self.item.key else None
    async def create(self,item):return item
    async def update(self,item):return item

class SkillRepo(AgentRepo):pass

class ExecutionRepo:
    def __init__(self):self.items={};self.events={}
    async def get(self,id):return self.items.get(id)
    async def create(self,item):self.items[item.id]=item;return item
    async def update(self,item):self.items[item.id]=item;return item
    async def add_event(self,id,event_type,payload):self.events.setdefault(id,[]).append({"event_type":event_type,"payload":payload,"created_at":datetime.now(timezone.utc).isoformat()})
    async def list_events(self,id):return self.events.get(id,[])

class Provider:
    async def generate(self,request:ModelRequest):
        return ModelResult(content="# LangGraph\nOK",model="test-model",usage=ModelUsage(input_tokens=10,output_tokens=4),provider_request_id="lg_1")

@pytest.mark.asyncio
async def test_langgraph_runtime_preserves_platform_contract():
    skill=SkillDefinition(key="analyze-opportunity",name="Analyze",objective="Analyze",instructions="Return analysis")
    agent=AgentDefinition(key="business-analyst",name="Business Analyst",role="Analyze opportunities",skills=[skill.key])
    ar=AgentRepo(agent);sr=SkillRepo(skill);er=ExecutionRepo()
    runtime=LangGraphAgentRuntime(AgentRegistry(ar,sr),SkillRegistry(sr),er,Provider(),checkpointer=MemorySaver())
    result=await runtime.execute(AgentExecutionRequest(agent_key=agent.key,skill_key=skill.key,objective="Test LangGraph"))
    assert result.status is ExecutionStatus.COMPLETED
    assert result.artifacts[0].content=="# LangGraph\nOK"
    persisted=await er.get(result.execution_id)
    assert persisted.runtime=="langgraph-v1"
    event_types=[event["event_type"] for event in await er.list_events(result.execution_id)]
    assert "langgraph.execution.started" in event_types
    assert "langgraph.node.context.completed" in event_types
    assert "langgraph.node.model.completed" in event_types
    assert "langgraph.execution.completed" in event_types
