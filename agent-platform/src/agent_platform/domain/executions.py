from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExecutionStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Attachment(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    content: str | None = None
    uri: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentExecutionCommandEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1"
    message_type: str = "agent.execution.command"
    application: str
    execution_id: UUID
    request: "AgentExecutionRequest"


class AgentExecutionEventEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1"
    message_type: str = "agent.execution.event"
    execution_id: UUID
    event_type: str
    source_event_type: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentExecutionRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    execution_id: UUID | None = None
    correlation_id: UUID | None = None
    agent_key: str = Field(min_length=1)
    skill_key: str | None = None
    objective: str = Field(min_length=1)
    model: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    attachments: list[Attachment] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)


class AgentArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: str = Field(min_length=1)
    name: str | None = None
    media_type: str = "text/markdown"
    content: str | None = None
    uri: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_content_or_uri(self):
        if not (self.content and self.content.strip()) and not (self.uri and self.uri.strip()):
            raise ValueError("AgentArtifact requires content or uri")
        return self


class AgentUsage(BaseModel):
    model_config = ConfigDict(frozen=True)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cache_read_tokens: int = Field(default=0, ge=0)
    cache_write_tokens: int = Field(default=0, ge=0)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.cache_read_tokens + self.cache_write_tokens


class AgentError(BaseModel):
    model_config = ConfigDict(frozen=True)
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class AgentExecution(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: UUID = Field(default_factory=uuid4)
    correlation_id: UUID | None = None
    agent_key: str = Field(min_length=1)
    skill_key: str | None = None
    status: ExecutionStatus = ExecutionStatus.QUEUED
    objective: str = Field(min_length=1)
    runtime: str | None = None
    model: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    usage: AgentUsage = Field(default_factory=AgentUsage)
    provider_request_id: str | None = None
    trace_id: str | None = None
    error: AgentError | None = None


class AgentExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    execution_id: UUID
    status: ExecutionStatus
    artifacts: list[AgentArtifact] = Field(default_factory=list)
    usage: AgentUsage = Field(default_factory=AgentUsage)
    model: str | None = None
    provider_request_id: str | None = None
    trace_id: str | None = None
    error: AgentError | None = None

AgentExecutionCommandEnvelope.model_rebuild()
