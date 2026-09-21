import asyncio
from datetime import datetime, timezone
from uuid import UUID

import pytest
from langgraph.checkpoint.memory import MemorySaver

from agent_platform.application.cache import CacheService, InMemoryCacheProvider
from agent_platform.application.langgraph_runtime import LangGraphAgentRuntime
from agent_platform.application.proposal_graph import ProposalPlanError, configured_sections, _section_body, _section_budget, _approved_artifacts, _section_context
from agent_platform.application.models import ModelRequest, ModelResult, ModelUsage
from agent_platform.application.registries import AgentRegistry, SkillRegistry
from agent_platform.config import Settings
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
    skill=SkillDefinition(key="qualify-opportunity",name="Qualify",objective="Qualify",instructions="Return qualification")
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


@pytest.mark.asyncio
async def test_langgraph_publishes_normalized_document():
    class WrappedProvider:
        async def generate(self, request):
            fence = chr(96) * 3
            return ModelResult(content=f"# delivery-plan.md\n\n{fence}markdown\n# Plan\nContent\n{fence}", model="test-model")

    skill=SkillDefinition(key="plan-delivery",name="Delivery",objective="Delivery",instructions="Draft")
    agent=AgentDefinition(key="delivery-manager",name="Delivery",role="Plan",skills=[skill.key])
    ar=AgentRepo(agent);sr=SkillRepo(skill);er=ExecutionRepo()
    runtime=LangGraphAgentRuntime(AgentRegistry(ar,sr),SkillRegistry(sr),er,WrappedProvider(),checkpointer=MemorySaver())
    result=await runtime.execute(AgentExecutionRequest(agent_key=agent.key,skill_key=skill.key,objective="Draft",constraints={"output_format":"markdown"}))
    assert result.status is ExecutionStatus.COMPLETED
    assert result.artifacts[0].content == "# Plan\nContent"


class ProposalProvider:
    def __init__(self, issues=False, revise_once=False):
        self.calls=[]
        self.issues=issues
        self.revise_once=revise_once

    async def generate(self, request: ModelRequest):
        stage=request.messages[0].content.split("# Current stage\n")[-1]
        self.calls.append(stage)
        if stage.startswith("Build an INTERNAL compact proposal context pack"):
            content='{"customerAndOpportunity":{"customer":"Example"},"mandatoryRequirements":[],"goalsAndScope":[],"responseStrategy":[],"solutionHighlights":[],"architectureAndIntegrations":[],"securityAndOperations":[],"deliveryApproach":[],"risksAssumptionsAndTbds":[],"differentiators":[],"evidenceIndex":{}}'
        elif stage.startswith("Write ONLY the body"):
            content="Evidence-backed draft."
        elif stage.startswith("Review ONLY section"):
            content='{"issues":[]}'
        elif stage.startswith("Review the complete proposal"):
            needs_revision=self.issues or (self.revise_once and sum(s.startswith("Review the complete proposal") for s in self.calls)==1)
            content='{"issues":[{"section":"Technical approach","severity":"BLOCKING","instruction":"Clarify coverage"}]}' if needs_revision else '{"issues":[]}'
        else:
            content="Evidence-backed revised body."
        return ModelResult(content=content,model="test-model",usage=ModelUsage(input_tokens=10,output_tokens=4))


@pytest.mark.asyncio
async def test_proposal_graph_preserves_configured_order_and_usage():
    skill=SkillDefinition(key="compose-proposal",name="Compose",objective="Proposal",instructions="Compose proposal")
    agent=AgentDefinition(key="business-analyst",name="BA",role="Writer",skills=[skill.key])
    er=ExecutionRepo();provider=ProposalProvider()
    runtime=LangGraphAgentRuntime(AgentRegistry(AgentRepo(agent),SkillRepo(skill)),SkillRegistry(SkillRepo(skill)),er,provider,checkpointer=MemorySaver())
    guidance='{"sections":[{"name":"Executive summary","depth":"SUMMARY"},{"name":"Ignored","enabled":false},{"name":"Technical approach","depth":"DETAILED","guidance":"Explain integrations"}]}'
    request=AgentExecutionRequest(agent_key=agent.key,skill_key=skill.key,objective="Compose",context={"business_context":"Offer name: Example\n# PROPOSAL GUIDANCE JSON\n"+guidance})
    result=await runtime.execute(request)
    assert result.status is ExecutionStatus.COMPLETED
    content=result.artifacts[0].content
    assert content.startswith("# Example\n\n## Executive summary\n")
    assert content.index("## Executive summary") < content.index("## Technical approach")
    assert "Ignored" not in content
    assert result.usage.input_tokens==60
    assert [e["event_type"] for e in await er.list_events(result.execution_id)].count("proposal.section.reviewed")==2


@pytest.mark.asyncio
async def test_proposal_global_review_corrects_issues_without_non_convergent_failure():
    skill=SkillDefinition(key="compose-proposal",name="Compose",objective="Proposal",instructions="Compose")
    agent=AgentDefinition(key="business-analyst",name="BA",role="Writer",skills=[skill.key])
    er=ExecutionRepo();provider=ProposalProvider(issues=True)
    runtime=LangGraphAgentRuntime(AgentRegistry(AgentRepo(agent),SkillRepo(skill)),SkillRegistry(SkillRepo(skill)),er,provider,checkpointer=MemorySaver())
    request=AgentExecutionRequest(agent_key=agent.key,skill_key=skill.key,objective="Compose",context={"business_context":"# PROPOSAL GUIDANCE JSON\n"+'{"sections":[{"name":"Technical approach"}]}'})
    result=await runtime.execute(request)
    assert result.status is ExecutionStatus.COMPLETED
    assert "## Technical approach\n\nEvidence-backed revised body." in result.artifacts[0].content
    events=await er.list_events(result.execution_id)
    assert any(e["event_type"]=="proposal.section.revised" for e in events)
    assert any(e["event_type"]=="proposal.global.review.corrected" for e in events)
    assert result.usage.input_tokens==50


@pytest.mark.asyncio
async def test_proposal_global_review_revises_only_affected_section():
    skill=SkillDefinition(key="compose-proposal",name="Compose",objective="Proposal",instructions="Compose")
    agent=AgentDefinition(key="business-analyst",name="BA",role="Writer",skills=[skill.key])
    er=ExecutionRepo();provider=ProposalProvider(revise_once=True)
    runtime=LangGraphAgentRuntime(AgentRegistry(AgentRepo(agent),SkillRepo(skill)),SkillRegistry(SkillRepo(skill)),er,provider,checkpointer=MemorySaver())
    request=AgentExecutionRequest(agent_key=agent.key,skill_key=skill.key,objective="Compose",context={"business_context":"# PROPOSAL GUIDANCE JSON\n"+'{"sections":[{"name":"Executive summary"},{"name":"Technical approach"}]}'})
    result=await runtime.execute(request)
    assert result.status is ExecutionStatus.COMPLETED
    assert "## Technical approach\n\nEvidence-backed revised body." in result.artifacts[0].content
    assert "## Executive summary\n\nEvidence-backed draft." in result.artifacts[0].content
    assert result.usage.input_tokens==70


def test_proposal_rejects_missing_or_invalid_guidance():
    with pytest.raises(ProposalPlanError):
        configured_sections(AgentExecutionRequest(agent_key="ba",objective="Compose"))
    with pytest.raises(ProposalPlanError):
        configured_sections(AgentExecutionRequest(agent_key="ba",objective="Compose",context={"business_context":"# PROPOSAL GUIDANCE JSON\n"+'{"sections":[{"name":"Same"},{"name":"Same"}]}' }))


class ProposalRetrievalService:
    def __init__(self):
        self.queries=[]

    async def retrieve(self, query):
        from agent_platform.domain import RetrievalHit, RetrievalResult
        from uuid import uuid4
        self.queries.append(query)
        section=(query.filters.metadata.get("enrichment") or {}).get("section_type")
        if section=="ARCHITECTURE":
            return RetrievalResult(
                query=query.text,
                mode=query.mode,
                hits=[RetrievalHit(
                    chunk_id=uuid4(),
                    document_id=uuid4(),
                    knowledge_base_key="reference-offers",
                    title="Reference RFP",
                    content="Reference architecture uses layered explanation.",
                    score=0.8,
                    retrieval_method=query.mode,
                    metadata={"enrichment":{"section_type":"ARCHITECTURE"}},
                    source_uri="upload://reference.pdf",
                )],
                metadata={"relevance_filtering":True,"vector_candidates":1,"keyword_candidates":1,"graph_candidates":0},
            )
        return RetrievalResult(
            query=query.text,
            mode=query.mode,
            hits=[],
            metadata={"relevance_filtering":True,"vector_candidates":0,"keyword_candidates":0,"graph_candidates":0},
        )


@pytest.mark.asyncio
async def test_proposal_graph_retrieves_section_reference_as_non_factual_context():
    skill=SkillDefinition(key="compose-proposal",name="Compose",objective="Proposal",instructions="Compose proposal")
    agent=AgentDefinition(key="business-analyst",name="BA",role="Writer",skills=[skill.key])
    er=ExecutionRepo();provider=ProposalProvider();retrieval=ProposalRetrievalService()
    runtime=LangGraphAgentRuntime(
        AgentRegistry(AgentRepo(agent),SkillRepo(skill)),
        SkillRegistry(SkillRepo(skill)),
        er,
        provider,
        checkpointer=MemorySaver(),
        proposal_retrieval_service=retrieval,
    )
    guidance='{"sections":[{"name":"Arquitectura","depth":"DETAILED","guidance":"Explica componentes e integraciones"}]}'
    request=AgentExecutionRequest(
        agent_key=agent.key,
        skill_key=skill.key,
        objective="Compose",
        context={"business_context":"Offer name: Example\n# PROPOSAL GUIDANCE JSON\n"+guidance},
    )
    result=await runtime.execute(request)

    assert result.status is ExecutionStatus.COMPLETED
    assert retrieval.queries
    assert retrieval.queries[0].filters.knowledge_base_keys==["reference-offers"]
    assert retrieval.queries[0].filters.metadata["enrichment"]["section_type"]=="ARCHITECTURE"
    assert any("NON-FACTUAL" in call and "Reference RFP" in call for call in provider.calls)
    events=await er.list_events(result.execution_id)
    retrieval_events=[e for e in events if e["event_type"]=="proposal.section.retrieval"]
    assert retrieval_events
    assert retrieval_events[0]["payload"]["hits"][0]["title"]=="Reference RFP"
    assert any(e["event_type"]=="proposal.retrieval.summary" for e in events)


@pytest.mark.asyncio
async def test_proposal_graph_falls_back_cleanly_when_no_reference_is_relevant():
    skill=SkillDefinition(key="compose-proposal",name="Compose",objective="Proposal",instructions="Compose proposal")
    agent=AgentDefinition(key="business-analyst",name="BA",role="Writer",skills=[skill.key])
    er=ExecutionRepo();provider=ProposalProvider();retrieval=ProposalRetrievalService()
    runtime=LangGraphAgentRuntime(
        AgentRegistry(AgentRepo(agent),SkillRepo(skill)),
        SkillRegistry(SkillRepo(skill)),
        er,
        provider,
        checkpointer=MemorySaver(),
        proposal_retrieval_service=retrieval,
    )
    guidance='{"sections":[{"name":"Próximos pasos","depth":"SUMMARY"}]}'
    request=AgentExecutionRequest(
        agent_key=agent.key,
        skill_key=skill.key,
        objective="Compose",
        context={"business_context":"# PROPOSAL GUIDANCE JSON\n"+guidance},
    )
    result=await runtime.execute(request)

    assert result.status is ExecutionStatus.COMPLETED
    events=await er.list_events(result.execution_id)
    section_event=next(e for e in events if e["event_type"]=="proposal.section.retrieval")
    assert section_event["payload"]["hits"]==[]


@pytest.mark.asyncio
async def test_proposal_graph_serializes_db_bound_retrieval_and_event_persistence():
    class GuardedExecutionRepo(ExecutionRepo):
        def __init__(self):
            super().__init__()
            self.active = 0
            self.max_active = 0

        async def add_event(self, id, event_type, payload):
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            if self.active > 1:
                self.active -= 1
                raise RuntimeError("concurrent AsyncSession use")
            try:
                await asyncio.sleep(0.005)
                await super().add_event(id, event_type, payload)
            finally:
                self.active -= 1

    class GuardedRetrieval(ProposalRetrievalService):
        def __init__(self):
            super().__init__()
            self.active = 0
            self.max_active = 0

        async def retrieve(self, query):
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            if self.active > 1:
                self.active -= 1
                raise RuntimeError("concurrent AsyncSession use")
            try:
                await asyncio.sleep(0.005)
                return await super().retrieve(query)
            finally:
                self.active -= 1

    skill=SkillDefinition(key="compose-proposal",name="Compose",objective="Proposal",instructions="Compose proposal")
    agent=AgentDefinition(key="business-analyst",name="BA",role="Writer",skills=[skill.key])
    er=GuardedExecutionRepo();provider=ProposalProvider();retrieval=GuardedRetrieval()
    runtime=LangGraphAgentRuntime(
        AgentRegistry(AgentRepo(agent),SkillRepo(skill)),
        SkillRegistry(SkillRepo(skill)),
        er,
        provider,
        checkpointer=MemorySaver(),
        proposal_retrieval_service=retrieval,
    )
    guidance='{"sections":[{"name":"Arquitectura"},{"name":"Seguridad"},{"name":"Próximos pasos"}]}'
    result=await runtime.execute(AgentExecutionRequest(
        agent_key=agent.key,
        skill_key=skill.key,
        objective="Compose",
        context={"business_context":"Offer name: Example\n# PROPOSAL GUIDANCE JSON\n"+guidance},
    ))

    assert result.status is ExecutionStatus.COMPLETED
    assert retrieval.max_active == 1
    assert er.max_active == 1


def test_proposal_section_body_normalizes_repeated_heading_and_nested_h2():
    raw = """# Requisitos y condicionantes:

Contenido principal.

## Requisitos funcionales
- Requisito A

## Condicionantes técnicos
- Condicionante B
"""
    body = _section_body(raw, "Requisitos y condicionantes")

    assert not body.startswith("# Requisitos y condicionantes")
    assert "### Requisitos funcionales" in body
    assert "### Condicionantes técnicos" in body
    assert "Contenido principal." in body


def test_proposal_section_body_accepts_bold_repeated_h2_title():
    raw = """## **Requisitos y condicionantes**

Contenido respaldado por evidencia.
"""
    assert _section_body(raw, "Requisitos y condicionantes") == "Contenido respaldado por evidencia."


def test_proposal_section_budgets_are_bounded_below_agent_global_limit():
    summary = _section_budget("SUMMARY")
    standard = _section_budget("STANDARD")
    detailed = _section_budget("DETAILED")

    assert summary == {"words": 700, "tokens": 2200}
    assert standard == {"words": 1200, "tokens": 3600}
    assert detailed == {"words": 1800, "tokens": 5600}
    assert summary["tokens"] < standard["tokens"] < detailed["tokens"] < 16000


def test_unknown_proposal_depth_falls_back_to_standard_budget():
    assert _section_budget("UNKNOWN") == _section_budget("STANDARD")


@pytest.mark.asyncio
async def test_proposal_substeps_are_reused_across_new_execution_ids():
    skill=SkillDefinition(key="compose-proposal",name="Compose",objective="Proposal",instructions="Compose proposal")
    agent=AgentDefinition(key="business-analyst",name="BA",role="Writer",skills=[skill.key])
    er=ExecutionRepo();provider=ProposalProvider();cache=CacheService(InMemoryCacheProvider(),prefix="test")
    runtime=LangGraphAgentRuntime(
        AgentRegistry(AgentRepo(agent),SkillRepo(skill)),
        SkillRegistry(SkillRepo(skill)),
        er,
        provider,
        checkpointer=MemorySaver(),
        cache=cache,
    )
    guidance='{"sections":[{"name":"Executive summary","depth":"SUMMARY"},{"name":"Technical approach","depth":"DETAILED"}]}'
    request=AgentExecutionRequest(
        agent_key=agent.key,
        skill_key=skill.key,
        objective="Compose",
        context={"business_context":"Offer name: Example\n# PROPOSAL GUIDANCE JSON\n"+guidance},
    )

    first=await runtime.execute(request)
    first_call_count=len(provider.calls)
    second=await runtime.execute(request)

    assert first.status is ExecutionStatus.COMPLETED
    assert second.status is ExecutionStatus.COMPLETED
    assert len(provider.calls)==first_call_count
    assert second.usage.input_tokens==0
    assert second.usage.output_tokens==0
    events=await er.list_events(second.execution_id)
    assert any(event["event_type"]=="proposal.step.reused" for event in events)


def test_proposal_context_selects_only_relevant_canonical_artifacts():
    pack = {
        "opportunityBrief": "Customer needs and scope",
        "questions": "Open questions",
        "technology": "Technology constraints",
        "solution": "Approved technical solution",
        "deliveryPlan": "Approved delivery plan",
    }
    architecture = _section_context(pack, {"name": "Arquitectura e integraciones", "guidance": "Detalle técnico"})
    delivery = _section_context(pack, {"name": "Enfoque de ejecución", "guidance": "Workstreams y metodología"})

    assert "solution" in architecture
    assert "technology" in architecture
    assert "deliveryPlan" not in architecture
    assert "deliveryPlan" in delivery
    assert "technology" not in delivery
    assert "opportunityBrief" in architecture


def test_approved_artifacts_are_parsed_deterministically():
    request = AgentExecutionRequest(
        agent_key="ba",
        objective="Compose",
        context={"business_context":
            "Offer name: Example\n\n"
            "# APPROVED OFFER ARTIFACTS\n"
            "# OPPORTUNITY_BRIEF\nBrief\n\n"
            "# SOLUTION\nSolution\n\n"
            "# DELIVERY_PLAN\nDelivery\n\n"
            "# PROPOSAL GUIDANCE JSON\n{\"sections\":[]}"
        },
    )
    pack = _approved_artifacts(request)
    assert pack["opportunityBrief"] == "Brief"
    assert pack["solution"] == "Solution"
    assert pack["deliveryPlan"] == "Delivery"


@pytest.mark.asyncio
async def test_proposal_cost_budget_stops_additional_generation(monkeypatch):
    import agent_platform.application.proposal_graph as proposal_graph

    guarded = Settings(
        database_url="postgresql+asyncpg://ignored",
        proposal_input_token_budget=250000,
        proposal_output_token_budget=30000,
        proposal_cost_budget_usd=0.000001,
    )
    monkeypatch.setattr(proposal_graph, "get_settings", lambda: guarded)

    skill=SkillDefinition(key="compose-proposal",name="Compose",objective="Proposal",instructions="Compose proposal")
    agent=AgentDefinition(key="business-analyst",name="BA",role="Writer",skills=[skill.key])
    er=ExecutionRepo();provider=ProposalProvider()
    runtime=LangGraphAgentRuntime(
        AgentRegistry(AgentRepo(agent),SkillRepo(skill)),
        SkillRegistry(SkillRepo(skill)),
        er,
        provider,
        checkpointer=MemorySaver(),
    )
    guidance='{"sections":[{"name":"Executive summary","depth":"SUMMARY"}]}'
    result=await runtime.execute(AgentExecutionRequest(
        agent_key=agent.key,
        skill_key=skill.key,
        objective="Compose",
        context={"business_context":"Offer name: Example\n# PROPOSAL GUIDANCE JSON\n"+guidance},
    ))

    assert result.status is ExecutionStatus.FAILED
    assert result.error is not None
    assert "budget" in result.error.message.lower()
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_proposal_single_mode_uses_one_model_call_and_keeps_coherent_document():
    class SinglePassProvider:
        def __init__(self):
            self.calls = 0
        async def generate(self, request: ModelRequest):
            self.calls += 1
            return ModelResult(
                content="# Example\n\n## Executive summary\n\nOne coherent proposal.\n\n## Technical approach\n\nIntegrated solution narrative.",
                model="test-model",
                usage=ModelUsage(input_tokens=50, output_tokens=30),
            )

    skill=SkillDefinition(key="compose-proposal",name="Compose",objective="Proposal",instructions="Compose proposal")
    agent=AgentDefinition(key="business-analyst",name="BA",role="Writer",skills=[skill.key])
    er=ExecutionRepo();provider=SinglePassProvider()
    runtime=LangGraphAgentRuntime(
        AgentRegistry(AgentRepo(agent),SkillRepo(skill)),
        SkillRegistry(SkillRepo(skill)),
        er,
        provider,
        checkpointer=MemorySaver(),
    )
    guidance='{"sections":[{"name":"Executive summary","depth":"SUMMARY"},{"name":"Technical approach","depth":"DETAILED"}]}'
    result=await runtime.execute(AgentExecutionRequest(
        agent_key=agent.key,
        skill_key=skill.key,
        objective="Compose",
        context={"business_context":
            "Offer name: Example\n\n"
            "# PROPOSAL MODE\nSINGLE\n\n"
            "# APPROVED OFFER ARTIFACTS\nQualified context and approved solution.\n\n"
            "# PROPOSAL GUIDANCE JSON\n"+guidance
        },
    ))

    assert result.status is ExecutionStatus.COMPLETED
    assert provider.calls == 1
    assert result.artifacts[0].content.startswith("# Example")
    events=await er.list_events(result.execution_id)
    assert any(event["event_type"]=="proposal.single_pass" for event in events)
    assert not any(event["event_type"]=="proposal.section.drafted" for event in events)


@pytest.mark.asyncio
async def test_proposal_single_mode_uses_one_business_analyst_generation():
    class SinglePassProvider:
        def __init__(self): self.calls=[]
        async def generate(self, request: ModelRequest):
            stage=request.messages[0].content.split("# Current stage\n")[-1]
            self.calls.append(stage)
            return ModelResult(
                content="# Example\n\n## Executive summary\n\nCoherent summary.\n\n## Solution\n\nCoherent solution.",
                model="test-model",
                usage=ModelUsage(input_tokens=20,output_tokens=10),
            )

    skill=SkillDefinition(key="compose-proposal",name="Compose",objective="Proposal",instructions="Compose proposal")
    agent=AgentDefinition(key="business-analyst",name="BA",role="Writer",skills=[skill.key])
    provider=SinglePassProvider();er=ExecutionRepo()
    runtime=LangGraphAgentRuntime(
        AgentRegistry(AgentRepo(agent),SkillRepo(skill)),
        SkillRegistry(SkillRepo(skill)),
        er,
        provider,
        checkpointer=MemorySaver(),
    )
    guidance='{"sections":[{"name":"Executive summary","depth":"SUMMARY"},{"name":"Solution","depth":"STANDARD"}]}'
    result=await runtime.execute(AgentExecutionRequest(
        agent_key=agent.key,
        skill_key=skill.key,
        objective="Compose",
        context={"business_context":"Offer name: Example\n\n# PROPOSAL MODE\nSINGLE\n\n# APPROVED OFFER ARTIFACTS\nBrief and solution.\n\n# PROPOSAL GUIDANCE JSON\n"+guidance},
        constraints={"output_format":"markdown"},
    ))

    assert result.status is ExecutionStatus.COMPLETED
    assert len(provider.calls)==1
    assert result.artifacts[0].content.startswith("# Example")
    events=await er.list_events(result.execution_id)
    assert any(event["event_type"]=="proposal.single_pass" for event in events)
