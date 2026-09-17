import pytest
from pydantic import ValidationError

from agent_platform.domain import AgentDefinition, SkillDefinition


def test_agent_definition_is_provider_agnostic_and_versioned() -> None:
    agent = AgentDefinition(
        key="openshift-specialist",
        name="OpenShift Specialist",
        role="Review OpenShift architecture and provide specialist guidance.",
        capabilities=["openshift", "kubernetes", "platform-engineering"],
        skills=["review-openshift-architecture"],
        knowledge_scopes=["architecture-references"],
        allowed_tools=["redhat-docs"],
    )

    assert agent.version == 1
    assert agent.enabled is True
    assert agent.model_policy.preferred_model is None
    assert agent.constraints.allow_tool_calls is True


def test_skill_definition_declares_knowledge_and_tools() -> None:
    skill = SkillDefinition(
        key="analyze-competitors",
        name="Analyze competitors",
        objective="Identify relevant competitor approaches using verifiable evidence.",
        instructions="Retrieve evidence, compare capabilities and separate facts from inference.",
        inputs=["sector", "problem"],
        knowledge_sources=["reference-offers", "market-intelligence"],
        allowed_tools=["web-search"],
        output_schema={"type": "object"},
    )

    assert skill.knowledge_sources == ["reference-offers", "market-intelligence"]
    assert skill.allowed_tools == ["web-search"]


def test_definition_keys_use_stable_slug_format() -> None:
    with pytest.raises(ValidationError):
        AgentDefinition(key="OpenShift Specialist", name="Invalid", role="Invalid key")
