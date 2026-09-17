import json
from typing import Any

from agent_platform.application.models import ModelMessage, ModelRequest, ModelRole
from agent_platform.domain import (
    AgentDefinition,
    AgentExecutionRequest,
    CognitiveContext,
    CognitiveSection,
    SkillDefinition,
)


_SECTION_TITLES = {
    CognitiveSection.BUSINESS_CONTEXT: "Business context",
    CognitiveSection.SOURCE_MATERIAL: "Source material",
    CognitiveSection.PRIOR_ARTIFACT: "Prior artifacts",
    CognitiveSection.MEMORY: "Relevant memory",
    CognitiveSection.RETRIEVED_KNOWLEDGE: "Retrieved knowledge",
    CognitiveSection.DECISION: "Relevant decisions",
    CognitiveSection.REFERENCE: "Reference material",
    CognitiveSection.TOOL_CONTEXT: "Tool context",
}


class AgentPromptAssembler:
    """Build a provider-neutral model request from definitions plus cognitive context."""

    def build(
        self,
        agent: AgentDefinition,
        skill: SkillDefinition | None,
        request: AgentExecutionRequest,
        cognitive_context: CognitiveContext | None = None,
    ) -> ModelRequest:
        system_sections = [f"# Agent\n{agent.name}", f"# Role\n{agent.role}"]
        if agent.description:
            system_sections.append(f"# Description\n{agent.description}")
        if agent.capabilities:
            system_sections.append("# Capabilities\n" + "\n".join(f"- {item}" for item in agent.capabilities))
        if skill is not None:
            system_sections.extend(
                [
                    f"# Skill\n{skill.name}",
                    f"# Skill objective\n{skill.objective}",
                    f"# Instructions\n{skill.instructions}",
                ]
            )
            if skill.output_schema:
                system_sections.append(
                    "# Expected output schema\n```json\n"
                    + json.dumps(skill.output_schema, ensure_ascii=False, indent=2, sort_keys=True)
                    + "\n```"
                )

        user_sections = [f"# Task\n{request.objective}"]
        context = cognitive_context or self._legacy_context(request)
        for section in CognitiveSection:
            items = context.by_section(section)
            if not items:
                continue
            rendered = []
            for item in items:
                rendered.append(
                    f"## {item.key}\nEpistemic label: {item.label.value}\nSource: {item.source}\n"
                    + self._render_content(item.content)
                )
            user_sections.append(f"# {_SECTION_TITLES[section]}\n" + "\n\n".join(rendered))

        if request.constraints:
            user_sections.append(
                "# Execution constraints\n```json\n"
                + json.dumps(request.constraints, ensure_ascii=False, indent=2, sort_keys=True, default=str)
                + "\n```"
            )

        return ModelRequest(
            system_prompt="\n\n".join(system_sections),
            messages=[ModelMessage(role=ModelRole.USER, content="\n\n".join(user_sections))],
            model=agent.model_policy.preferred_model,
            temperature=agent.model_policy.temperature,
            max_output_tokens=agent.model_policy.max_output_tokens,
            metadata={
                "agent_key": agent.key,
                "agent_version": agent.version,
                "skill_key": skill.key if skill else None,
                "skill_version": skill.version if skill else None,
                "correlation_id": str(request.correlation_id) if request.correlation_id else None,
                "cognitive_context": context.summary(),
            },
        )

    @staticmethod
    def _render_content(content: Any) -> str:
        if isinstance(content, str):
            return content
        return "```json\n" + json.dumps(content, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n```"

    @staticmethod
    def _legacy_context(request: AgentExecutionRequest) -> CognitiveContext:
        from agent_platform.application.cognitive import ApplicationContextContributor
        from agent_platform.domain import CognitiveContextItem, EpistemicLabel

        items: list[CognitiveContextItem] = []
        if request.context:
            items.append(
                CognitiveContextItem(
                    key="application-context",
                    section=CognitiveSection.BUSINESS_CONTEXT,
                    content=request.context,
                    source=ApplicationContextContributor.name,
                    priority=100,
                    required=True,
                    label=EpistemicLabel.UNCLASSIFIED,
                )
            )
        for index, attachment in enumerate(request.attachments):
            items.append(
                CognitiveContextItem(
                    key=f"attachment:{index}:{attachment.name}",
                    section=CognitiveSection.SOURCE_MATERIAL,
                    content={
                        "name": attachment.name,
                        "media_type": attachment.media_type,
                        "uri": attachment.uri,
                        "content": attachment.content,
                    },
                    source="attachments",
                    priority=95,
                    required=True,
                    metadata=attachment.metadata,
                )
            )
        return CognitiveContext(items=items)
