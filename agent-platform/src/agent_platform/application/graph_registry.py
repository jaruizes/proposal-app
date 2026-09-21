from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END


GraphBuilder = Callable[[Any, Any, Any], None]


class GraphRegistry:
    """Resolve the cognitive graph declared by a skill.

    Business workflow orchestration remains outside this registry. This registry
    only selects the internal cognitive topology for one AgentExecution.
    """

    DEFAULT_GRAPH = "resilient-single"

    @classmethod
    def graph_key(cls, skill) -> str:
        if skill is None or not isinstance(skill.constraints, dict):
            return cls.DEFAULT_GRAPH
        execution = skill.constraints.get("execution", {})
        if not isinstance(execution, dict):
            return cls.DEFAULT_GRAPH
        value = str(execution.get("graph") or cls.DEFAULT_GRAPH).strip()
        return value or cls.DEFAULT_GRAPH

    @classmethod
    def attach(cls, graph_key: str, builder, runtime, execution) -> None:
        if graph_key == "resilient-single":
            builder.add_edge("build_context", "invoke_model")
            builder.add_edge("invoke_model", END)
            return
        if graph_key == "proposal":
            from agent_platform.application.proposal_graph import add_proposal_nodes
            add_proposal_nodes(builder, runtime, execution)
            return
        if graph_key == "presentation-plan":
            from agent_platform.application.presentation_plan_graph import add_presentation_plan_nodes
            add_presentation_plan_nodes(builder, runtime, execution)
            return
        raise ValueError(
            f"Unknown cognitive graph {graph_key!r}. Register it in GraphRegistry before assigning it to a skill."
        )


__all__ = ["GraphRegistry"]
