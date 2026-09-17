from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MemoryScopeType(StrEnum):
    CORRELATION = "correlation"
    AGENT = "agent"
    GLOBAL = "global"
    CUSTOM = "custom"


class MemoryKind(StrEnum):
    OBSERVATION = "observation"
    FACT = "fact"
    DECISION = "decision"
    PREFERENCE = "preference"
    SUMMARY = "summary"
    EXECUTION_RESULT = "execution_result"


class MemoryScope(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: MemoryScopeType
    key: str = Field(min_length=1)


class MemoryEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    scope_type: MemoryScopeType
    scope_key: str = Field(min_length=1)
    kind: MemoryKind = MemoryKind.OBSERVATION
    content: str = Field(min_length=1)
    agent_key: str | None = None
    skill_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    active: bool = True
    expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class MemoryWrite(BaseModel):
    model_config = ConfigDict(frozen=True)

    scope_type: MemoryScopeType
    scope_key: str = Field(min_length=1)
    kind: MemoryKind = MemoryKind.OBSERVATION
    content: str = Field(min_length=1)
    agent_key: str | None = None
    skill_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    expires_at: datetime | None = None


class MemoryRecall(BaseModel):
    model_config = ConfigDict(frozen=True)

    scopes: list[MemoryScope] = Field(min_length=1)
    kinds: list[MemoryKind] = Field(default_factory=list)
    agent_key: str | None = None
    skill_key: str | None = None
    min_importance: float = Field(default=0.0, ge=0.0, le=1.0)
    limit: int = Field(default=10, ge=1, le=100)
    include_expired: bool = False
