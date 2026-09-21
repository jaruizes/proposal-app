from types import SimpleNamespace

import pytest

from agent_platform.application.models import ModelMessage, ModelProviderError, ModelRequest, ModelRole
from agent_platform.config import Settings
from agent_platform.providers.anthropic import AnthropicModelProvider


class FakeMessages:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.last_payload = None

    def stream(self, **payload):
        self.last_payload = payload
        return self

    async def __aenter__(self):
        if self.error:
            raise self.error
        return self

    async def __aexit__(self, *_):
        return False

    async def get_final_text(self):
        return "".join(block.text for block in self.response.content if block.type == "text")

    async def get_final_message(self):
        return self.response


class FakeClient:
    def __init__(self, messages: FakeMessages) -> None:
        self.messages = messages


def settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://ignored",
        anthropic_api_key="test-key",
        anthropic_default_model="claude-test",
        anthropic_default_max_output_tokens=2048,
    )


@pytest.mark.asyncio
async def test_anthropic_adapter_maps_request_response_and_usage() -> None:
    response = SimpleNamespace(
        id="msg_123",
        model="claude-test",
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text="Hello"), SimpleNamespace(type="text", text=" world")],
        usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=20,
            cache_read_input_tokens=30,
            cache_creation_input_tokens=10,
        ),
    )
    messages = FakeMessages(response=response)
    provider = AnthropicModelProvider(settings(), FakeClient(messages))

    result = await provider.generate(
        ModelRequest(
            system_prompt="You are helpful.",
            messages=[ModelMessage(role=ModelRole.USER, content="Hi")],
            temperature=0.1,
        )
    )

    assert messages.last_payload == {
        "model": "claude-test",
        "max_tokens": 2048,
        "messages": [{"role": "user", "content": "Hi"}],
        "system": "You are helpful.",
        "temperature": 0.1,
    }
    assert result.content == "Hello world"
    assert result.provider_request_id == "msg_123"
    assert result.usage.input_tokens == 100
    assert result.usage.output_tokens == 20
    assert result.usage.cache_read_tokens == 30
    assert result.usage.cache_write_tokens == 10
    assert result.metadata["provider"] == "anthropic"


@pytest.mark.asyncio
async def test_anthropic_adapter_normalizes_retryable_errors() -> None:
    RateLimitError = type("RateLimitError", (Exception,), {})
    provider = AnthropicModelProvider(settings(), FakeClient(FakeMessages(error=RateLimitError("slow down"))))

    with pytest.raises(ModelProviderError) as error:
        await provider.generate(ModelRequest(messages=[ModelMessage(role=ModelRole.USER, content="Hi")]))

    assert error.value.retryable is True
    assert error.value.code == "ANTHROPIC_RATELIMITERROR"


@pytest.mark.asyncio
async def test_anthropic_adapter_rejects_truncated_output() -> None:
    response = SimpleNamespace(
        id="msg_truncated", model="claude-test", stop_reason="max_tokens",
        content=[SimpleNamespace(type="text", text='{"opportunityBrief":"# Partial')],
        usage=SimpleNamespace(input_tokens=10, output_tokens=2048),
    )
    provider = AnthropicModelProvider(settings(), FakeClient(FakeMessages(response=response)))

    with pytest.raises(ModelProviderError) as error:
        await provider.generate(ModelRequest(messages=[ModelMessage(role=ModelRole.USER, content="Analyze")]))

    assert error.value.code == "ANTHROPIC_OUTPUT_TRUNCATED"


def test_anthropic_adapter_requires_api_key_without_injected_client() -> None:
    with pytest.raises(ModelProviderError) as error:
        AnthropicModelProvider(Settings(database_url="postgresql+asyncpg://ignored", anthropic_api_key=None))

    assert error.value.code == "ANTHROPIC_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_anthropic_adapter_marks_stable_system_and_context_for_prompt_cache() -> None:
    response = SimpleNamespace(
        id="msg_cache",
        model="claude-test",
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text="OK")],
        usage=SimpleNamespace(
            input_tokens=20,
            output_tokens=2,
            cache_read_input_tokens=120,
            cache_creation_input_tokens=0,
        ),
    )
    messages = FakeMessages(response=response)
    provider = AnthropicModelProvider(settings(), FakeClient(messages))

    await provider.generate(ModelRequest(
        system_prompt="Stable agent and skill instructions",
        cache_system_prompt=True,
        cacheable_context="Stable proposal context",
        messages=[ModelMessage(role=ModelRole.USER, content="Draft this section")],
    ))

    assert messages.last_payload["system"] == [{
        "type": "text",
        "text": "Stable agent and skill instructions",
        "cache_control": {"type": "ephemeral"},
    }]
    assert messages.last_payload["messages"][0]["content"][0] == {
        "type": "text",
        "text": "Stable proposal context",
        "cache_control": {"type": "ephemeral"},
    }
    assert messages.last_payload["messages"][0]["content"][1]["text"] == "Draft this section"
