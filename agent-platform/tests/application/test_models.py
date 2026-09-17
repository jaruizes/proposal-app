import pytest
from pydantic import ValidationError

from agent_platform.application.models import ModelMessage, ModelRequest, ModelResult, ModelRole, ModelUsage


def test_model_contract_is_provider_neutral() -> None:
    request = ModelRequest(
        system_prompt="You are a solution architect.",
        messages=[ModelMessage(role=ModelRole.USER, content="Design a resilient platform.")],
        model="preferred-model",
        temperature=0.2,
        max_output_tokens=2000,
        metadata={"agent": "solution-architect"},
    )

    assert request.messages[0].role is ModelRole.USER
    assert request.metadata["agent"] == "solution-architect"


def test_model_result_tracks_usage_and_cache_tokens() -> None:
    usage = ModelUsage(input_tokens=100, output_tokens=25, cache_read_tokens=40, cache_write_tokens=10)
    result = ModelResult(content="answer", model="model-x", usage=usage, provider_request_id="req-1")

    assert result.usage.total_tokens == 175
    assert result.provider_request_id == "req-1"


def test_model_request_requires_at_least_one_message() -> None:
    with pytest.raises(ValidationError):
        ModelRequest(messages=[])
