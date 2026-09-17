from uuid import uuid4

import pytest

from agent_platform.application.cognitive import (
    ApplicationContextContributor,
    CognitiveContextBuilder,
    KnowledgeRetrievalContributor,
)
from agent_platform.domain import (
    AgentDefinition,
    AgentExecutionRequest,
    CognitiveSection,
    EpistemicLabel,
    RetrievalHit,
    RetrievalMode,
    RetrievalResult,
    SkillDefinition,
)


class FakeRetrievalService:
    def __init__(self, result: RetrievalResult | None = None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.queries = []

    async def retrieve(self, query):
        self.queries.append(query)
        if self.error:
            raise self.error
        return self.result or RetrievalResult(query=query.text, mode=query.mode)


def agent() -> AgentDefinition:
    return AgentDefinition(key="business-analyst", name="Business Analyst", role="Analyze", skills=["analyze-opportunity"])


def skill(**overrides) -> SkillDefinition:
    values = {
        "key": "analyze-opportunity",
        "name": "Analyze opportunity",
        "objective": "Analyze the customer opportunity",
        "instructions": "Use relevant evidence and keep references attributable.",
        "knowledge_sources": ["reference-offers", "case-studies"],
    }
    values.update(overrides)
    return SkillDefinition(**values)


@pytest.mark.asyncio
async def test_retrieval_contributor_uses_skill_sources_and_marks_reference():
    document_id = uuid4()
    chunk_id = uuid4()
    parent_id = uuid4()
    service = FakeRetrievalService(
        RetrievalResult(
            query="Analyze the customer opportunity\n\nCurrent task: Analyze cloud migration",
            mode=RetrievalMode.HYBRID,
            embedding_model="hash-embedding-v1",
            hits=[
                RetrievalHit(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    knowledge_base_key="reference-offers",
                    title="Cloud migration offer",
                    content="A prior proposal used a phased migration approach.",
                    parent_chunk_id=parent_id,
                    parent_content="Prior proposal context for a phased migration.",
                    score=0.42,
                    retrieval_method=RetrievalMode.HYBRID,
                    source_uri="upload://cloud-offer.pdf",
                )
            ],
        )
    )
    contributor = KnowledgeRetrievalContributor(service)
    request = AgentExecutionRequest(agent_key="business-analyst", skill_key="analyze-opportunity", objective="Analyze cloud migration")

    items = await contributor.contribute(agent(), skill(), request)

    assert len(service.queries) == 1
    query = service.queries[0]
    assert query.filters.knowledge_base_keys == ["reference-offers", "case-studies"]
    assert query.mode is RetrievalMode.HYBRID
    assert query.expand_parents is True
    assert len(items) == 1
    assert items[0].section is CognitiveSection.RETRIEVED_KNOWLEDGE
    assert items[0].label is EpistemicLabel.REFERENCE
    assert items[0].source == "upload://cloud-offer.pdf"
    assert items[0].content["parent_context"] == "Prior proposal context for a phased migration."
    assert items[0].metadata["chunk_id"] == str(chunk_id)


@pytest.mark.asyncio
async def test_retrieval_config_is_owned_by_skill_constraints():
    service = FakeRetrievalService()
    configured_skill = skill(
        constraints={
            "retrieval": {
                "mode": "keyword",
                "top_k": 3,
                "candidate_k": 9,
                "expand_parents": False,
            }
        }
    )
    contributor = KnowledgeRetrievalContributor(service)
    request = AgentExecutionRequest(agent_key="business-analyst", skill_key="analyze-opportunity", objective="Find banking case studies")

    await contributor.contribute(agent(), configured_skill, request)

    query = service.queries[0]
    assert query.mode is RetrievalMode.KEYWORD
    assert query.top_k == 3
    assert query.candidate_k == 9
    assert query.expand_parents is False


@pytest.mark.asyncio
async def test_skill_without_knowledge_sources_does_not_retrieve():
    service = FakeRetrievalService()
    contributor = KnowledgeRetrievalContributor(service)
    request = AgentExecutionRequest(agent_key="business-analyst", skill_key="analyze-opportunity", objective="Analyze")

    items = await contributor.contribute(agent(), skill(knowledge_sources=[]), request)

    assert items == []
    assert service.queries == []


@pytest.mark.asyncio
async def test_retrieval_failure_is_optional_and_becomes_context_warning():
    service = FakeRetrievalService(error=RuntimeError("vector store unavailable"))
    builder = CognitiveContextBuilder(
        contributors=[ApplicationContextContributor(), KnowledgeRetrievalContributor(service)]
    )
    request = AgentExecutionRequest(
        agent_key="business-analyst",
        skill_key="analyze-opportunity",
        objective="Analyze",
        context={"customer": "ACME"},
    )

    context = await builder.build(agent(), skill(), request)

    assert context.by_section(CognitiveSection.BUSINESS_CONTEXT)
    assert context.by_section(CognitiveSection.RETRIEVED_KNOWLEDGE) == []
    assert context.warnings == ["knowledge-retrieval: vector store unavailable"]


@pytest.mark.asyncio
async def test_rag_items_flow_through_cognitive_summary():
    service = FakeRetrievalService(
        RetrievalResult(
            query="Analyze the customer opportunity\n\nCurrent task: Analyze",
            mode=RetrievalMode.HYBRID,
            hits=[
                RetrievalHit(
                    chunk_id=uuid4(),
                    document_id=uuid4(),
                    knowledge_base_key="case-studies",
                    title="Case study",
                    content="Reference content",
                    score=0.2,
                    retrieval_method=RetrievalMode.HYBRID,
                )
            ],
        )
    )
    builder = CognitiveContextBuilder(contributors=[KnowledgeRetrievalContributor(service)])
    request = AgentExecutionRequest(agent_key="business-analyst", skill_key="analyze-opportunity", objective="Analyze")

    context = await builder.build(agent(), skill(), request)
    summary = context.summary()

    assert summary["sections"]["retrieved_knowledge"] == 1
    assert summary["knowledge_sources"] == ["reference-offers", "case-studies"]
    assert context.items[0].label is EpistemicLabel.REFERENCE
