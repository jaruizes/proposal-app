import pytest

from langgraph.graph import StateGraph

from agent_platform.application.graph_registry import GraphRegistry
from agent_platform.domain import SkillDefinition


def skill(key: str, graph: str | None = None) -> SkillDefinition:
    constraints = {}
    if graph:
        constraints = {"execution": {"graph": graph}}
    return SkillDefinition(
        key=key,
        name=key,
        objective=key,
        instructions="test",
        constraints=constraints,
    )


def test_graph_registry_defaults_to_resilient_single():
    assert GraphRegistry.graph_key(skill("future-skill")) == "resilient-single"


def test_graph_registry_reads_declarative_skill_graph():
    assert GraphRegistry.graph_key(skill("compose-proposal", "proposal")) == "proposal"
    assert GraphRegistry.graph_key(skill("design-presentation", "presentation-plan")) == "presentation-plan"


def test_graph_registry_rejects_unknown_graph():
    builder = StateGraph(dict)
    with pytest.raises(ValueError, match="Unknown cognitive graph"):
        GraphRegistry.attach("investment-research", builder, object(), object())
