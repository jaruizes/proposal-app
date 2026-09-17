from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


class ModelRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ModelMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: ModelRole
    content: str = Field(min_length=1)


class ModelRequest(BaseModel):
    """Provider-neutral request for text generation."""

    model_config = ConfigDict(frozen=True)

    messages: list[ModelMessage] = Field(min_length=1)
    system_prompt: str | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_output_tokens: int | None = Field(default=None, gt=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelUsage(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cache_read_tokens: int = Field(default=0, ge=0)
    cache_write_tokens: int = Field(default=0, ge=0)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.cache_read_tokens + self.cache_write_tokens


class ModelResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    content: str
    model: str
    usage: ModelUsage = Field(default_factory=ModelUsage)
    provider_request_id: str | None = None
    finish_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelProviderError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class ModelProvider(Protocol):
    """Port implemented by concrete LLM providers or provider gateways."""

    async def generate(self, request: ModelRequest) -> ModelResult: ...
