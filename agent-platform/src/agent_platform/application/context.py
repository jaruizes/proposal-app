import json

from agent_platform.application.models import ModelMessage, ModelRequest, ModelRole
from agent_platform.domain import AgentDefinition, AgentExecutionRequest, SkillDefinition


class AgentPromptAssembler:
    """Build the provider-neutral model request from agent, skill and execution context."""

    def build(
        self,
        agent: AgentDefinition,
        skill: SkillDefinition | None,
        request: AgentExecutionRequest,
    ) -> ModelRequest:
        system_sections = [
            f"# Agent\n{agent.name}",
            f"# Role\n{agent.role}",
        ]
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
        if request.context:
            user_sections.append(
                "# Application context\n```json\n"
                + json.dumps(request.context, ensure_ascii=False, indent=2, sort_keys=True, default=str)
                + "\n```"
            )
        if request.attachments:
            attachment_lines = []
            for attachment in request.attachments:
                location = attachment.uri or "inline"
                attachment_lines.append(f"- {attachment.name} ({attachment.media_type}) [{location}]")
                if attachment.content:
                    attachment_lines.append(attachment.content)
            user_sections.append("# Attachments\n" + "\n".join(attachment_lines))
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
            },
        )
