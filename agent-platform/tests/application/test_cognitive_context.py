import asyncio
import pytest

from agent_platform.application.cognitive import CognitiveContextBuilder, CognitiveContextPolicy
from agent_platform.application.context import AgentPromptAssembler
from agent_platform.domain import (
    AgentDefinition,
    AgentExecutionRequest,
    CognitiveContextItem,
    CognitiveSection,
    EpistemicLabel,
    SkillDefinition,
)


class OptionalRetriever:
    name = "retrieval"
    required = False

    async def contribute(self, agent, skill, request):
        return [
            CognitiveContextItem(
                key="reference-offer-1",
                section=CognitiveSection.REFERENCE,
                content="Previous approved reference offer",
                label=EpistemicLabel.REFERENCE,
                source="reference-offers",
                priority=60,
            )
        ]


class BrokenOptionalContributor:
    name = "broken-memory"
    required = False

    async def contribute(self, agent, skill, request):
        raise RuntimeError("memory unavailable")


@pytest.mark.asyncio
async def test_builder_assembles_business_source_and_future_knowledge_intent() -> None:
    skill = SkillDefinition(
        key="build-strategy",
        name="Build strategy",
        objective="Build it",
        instructions="Use relevant evidence",
        knowledge_sources=["reference-offers", "corporate-capabilities"],
    )
    agent = AgentDefinition(
        key="business-analyst",
        name="Business Analyst",
        role="Offer Owner",
        skills=[skill.key],
        knowledge_scopes=["customer", "corporate"],
        allowed_tools=["source.read", "knowledge.search"],
    )
    request = AgentExecutionRequest(
        agent_key=agent.key,
        skill_key=skill.key,
        objective="Build response strategy",
        context={"customer": "Example Corp", "sector": "energy"},
    )

    context = await CognitiveContextBuilder(contributors=[OptionalRetriever()]).build(agent, skill, request)

    assert context.knowledge_sources == ["reference-offers", "corporate-capabilities"]
    assert context.knowledge_scopes == ["customer", "corporate"]
    assert context.allowed_tools == ["source.read", "knowledge.search"]
    assert context.items[0].label is EpistemicLabel.REFERENCE


@pytest.mark.asyncio
async def test_optional_contributor_failure_does_not_break_execution_context() -> None:
    agent = AgentDefinition(key="agent", name="Agent", role="Role")
    request = AgentExecutionRequest(agent_key="agent", objective="Work")
    context = await CognitiveContextBuilder(contributors=[BrokenOptionalContributor()]).build(agent, None, request)
    assert context.items == []
    assert context.warnings == ["broken-memory: memory unavailable"]


@pytest.mark.asyncio
async def test_budget_drops_optional_low_priority_context_but_never_required_context() -> None:
    class RequiredAndOptional:
        name = "mixed"
        required = True

        async def contribute(self, agent, skill, request):
            return [
                CognitiveContextItem(key="required", section=CognitiveSection.BUSINESS_CONTEXT, content="x" * 40, source="mixed", priority=100, required=True),
                CognitiveContextItem(key="optional", section=CognitiveSection.REFERENCE, content="y" * 40, source="mixed", priority=10),
            ]

    agent = AgentDefinition(key="agent", name="Agent", role="Role")
    request = AgentExecutionRequest(agent_key="agent", objective="Work")
    context = await CognitiveContextBuilder(
        contributors=[RequiredAndOptional()], policy=CognitiveContextPolicy(max_items=1, max_context_chars=10)
    ).build(agent, None, request)

    assert [item.key for item in context.items] == ["required"]
    assert context.dropped_items == ["optional"]


@pytest.mark.asyncio
async def test_prompt_assembler_renders_epistemic_provenance() -> None:
    agent = AgentDefinition(key="agent", name="Agent", role="Role")
    request = AgentExecutionRequest(agent_key="agent", objective="Work", context={"customer": "ACME"})
    context = await CognitiveContextBuilder().build(agent, None, request)
    model_request = AgentPromptAssembler().build(agent, None, request, context)

    assert "# Business context" in model_request.messages[0].content
    assert "Epistemic label: UNCLASSIFIED" in model_request.messages[0].content
    assert "Source: application-context" in model_request.messages[0].content
    assert '"customer": "ACME"' in model_request.messages[0].content


@pytest.mark.asyncio
async def test_builder_serializes_contributors_that_share_request_scoped_resources() -> None:
    active = 0
    max_active = 0

    class GuardedContributor:
        required = False

        def __init__(self, name: str) -> None:
            self.name = name

        async def contribute(self, agent, skill, request):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            try:
                await asyncio.sleep(0.01)
                return []
            finally:
                active -= 1

    agent = AgentDefinition(key="agent", name="Agent", role="Role")
    request = AgentExecutionRequest(agent_key="agent", objective="Work")
    await CognitiveContextBuilder(
        contributors=[GuardedContributor("memory"), GuardedContributor("retrieval")]
    ).build(agent, None, request)

    assert max_active == 1
