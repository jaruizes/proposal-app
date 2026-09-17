from agent_platform.application.context import AgentPromptAssembler
from agent_platform.domain import AgentDefinition, AgentExecutionRequest, ModelPolicy, SkillDefinition


def test_prompt_assembler_combines_agent_skill_and_application_context() -> None:
    agent = AgentDefinition(
        key="openshift-specialist",
        name="OpenShift Specialist",
        role="Act as a senior OpenShift architect.",
        capabilities=["openshift", "kubernetes"],
        model_policy=ModelPolicy(preferred_model="claude-test", temperature=0.1, max_output_tokens=2048),
    )
    skill = SkillDefinition(
        key="review-openshift-architecture",
        name="Review OpenShift architecture",
        objective="Review the proposed architecture.",
        instructions="Identify risks and recommend improvements.",
        output_schema={"type": "object", "properties": {"summary": {"type": "string"}}},
    )
    request = AgentExecutionRequest(
        agent_key=agent.key,
        skill_key=skill.key,
        objective="Review this OpenShift platform proposal.",
        context={"customer": "Acme", "nodes": 6},
    )

    model_request = AgentPromptAssembler().build(agent, skill, request)

    assert "Act as a senior OpenShift architect." in model_request.system_prompt
    assert "Identify risks and recommend improvements." in model_request.system_prompt
    assert '"customer": "Acme"' in model_request.messages[0].content
    assert model_request.model == "claude-test"
    assert model_request.temperature == 0.1
    assert model_request.max_output_tokens == 2048
    assert model_request.metadata["agent_key"] == "openshift-specialist"
