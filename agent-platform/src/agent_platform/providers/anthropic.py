from typing import Any

from anthropic import AsyncAnthropic

from agent_platform.application.models import (
    ModelProviderError,
    ModelRequest,
    ModelResult,
    ModelUsage,
)
from agent_platform.config import Settings, get_settings


class AnthropicModelProvider:
    """Anthropic Messages API adapter behind the provider-neutral model port."""

    def __init__(self, settings: Settings | None = None, client: Any | None = None) -> None:
        self._settings = settings or get_settings()
        if client is not None:
            self._client = client
            return
        if not self._settings.anthropic_api_key:
            raise ModelProviderError(
                "ANTHROPIC_NOT_CONFIGURED",
                "ANTHROPIC_API_KEY is required to use the Anthropic provider",
            )
        kwargs: dict[str, Any] = {
            "api_key": self._settings.anthropic_api_key,
            "timeout": self._settings.anthropic_timeout_seconds,
        }
        if self._settings.anthropic_base_url:
            kwargs["base_url"] = self._settings.anthropic_base_url
        self._client = AsyncAnthropic(**kwargs)

    async def generate(self, request: ModelRequest) -> ModelResult:
        model = request.model or self._settings.anthropic_default_model
        max_tokens = request.max_output_tokens or self._settings.anthropic_default_max_output_tokens
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": message.role.value, "content": message.content}
                for message in request.messages
            ],
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt
        if request.temperature is not None:
            payload["temperature"] = request.temperature

        try:
            response = await self._client.messages.create(**payload)
        except Exception as exc:
            name = type(exc).__name__
            retryable = name in {
                "APITimeoutError",
                "APIConnectionError",
                "RateLimitError",
                "InternalServerError",
                "OverloadedError",
            }
            raise ModelProviderError(
                f"ANTHROPIC_{name.upper()}",
                str(exc) or "Anthropic request failed",
                retryable=retryable,
            ) from exc

        text = "".join(
            getattr(block, "text", "")
            for block in response.content
            if getattr(block, "type", None) == "text"
        )
        usage = getattr(response, "usage", None)
        return ModelResult(
            content=text,
            model=getattr(response, "model", model),
            usage=ModelUsage(
                input_tokens=getattr(usage, "input_tokens", 0) or 0,
                output_tokens=getattr(usage, "output_tokens", 0) or 0,
                cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
                cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            ),
            provider_request_id=getattr(response, "id", None),
            finish_reason=getattr(response, "stop_reason", None),
            metadata={"provider": "anthropic"},
        )
