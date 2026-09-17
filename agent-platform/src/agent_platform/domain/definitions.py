from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ModelPolicy(BaseModel):
    """Model preferences without coupling the domain to a model provider."""

    model_config = ConfigDict(frozen=True)

    preferred_model: str | None = None
    fallback_models: list[str] = Field(default_factory=list)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_output_tokens: int | None = Field(default=None, gt=0)


class AgentConstraints(BaseModel):
    """Execution limits owned by the platform rather than by a specific runtime."""

    model_config = ConfigDict(frozen=True)

    max_delegations: int = Field(default=0, ge=0)
    allow_web: bool = False
    allow_tool_calls: bool = True
    extra: dict[str, Any] = Field(default_factory=dict)


class AgentDefinition(BaseModel):
    """Versioned, configurable definition of an agent."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    key: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1)
    description: str = ""
    role: str = Field(min_length=1)
    capabilities: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    knowledge_scopes: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    model_policy: ModelPolicy = Field(default_factory=ModelPolicy)
    constraints: AgentConstraints = Field(default_factory=AgentConstraints)
    version: int = Field(default=1, ge=1)
    enabled: bool = True


class SkillDefinition(BaseModel):
    """Reusable task contract that describes how an agent performs bounded work."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    key: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1)
    description: str = ""
    objective: str = Field(min_length=1)
    instructions: str = Field(min_length=1)
    inputs: list[str] = Field(default_factory=list)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    knowledge_sources: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    version: int = Field(default=1, ge=1)
    enabled: bool = True
