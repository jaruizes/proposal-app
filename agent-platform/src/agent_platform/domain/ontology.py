from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OntologyTargetType(StrEnum):
    DOCUMENT = "document"
    CHUNK = "chunk"


class OntologyConcept(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: UUID = Field(default_factory=uuid4)
    key: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    name: str = Field(min_length=1)
    type: str = Field(min_length=1)
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    created_at: datetime = Field(default_factory=utc_now)


class OntologyRelationship(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: UUID = Field(default_factory=uuid4)
    source_key: str = Field(min_length=1)
    relation: str = Field(min_length=1, pattern=r"^[A-Z][A-Z0-9_]*$")
    target_key: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class OntologyMapping(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: UUID = Field(default_factory=uuid4)
    target_type: OntologyTargetType
    target_id: UUID
    concept_key: str = Field(min_length=1)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: str = "deterministic"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
