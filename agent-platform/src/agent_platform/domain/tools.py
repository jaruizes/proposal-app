from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ToolDefinition(BaseModel):
    """Provider-neutral description of a callable tool."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    provider: str = Field(min_length=1)
    server: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class ToolCall(BaseModel):
    """One tool invocation requested by the platform/runtime."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    tool_key: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    correlation_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolError(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Normalized result returned by any tool provider."""

    model_config = ConfigDict(frozen=True)

    call_id: UUID
    tool_key: str
    content: list[dict[str, Any]] = Field(default_factory=list)
    structured_content: Any | None = None
    is_error: bool = False
    error: ToolError | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
