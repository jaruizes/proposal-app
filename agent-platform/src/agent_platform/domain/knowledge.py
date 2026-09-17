from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeDocumentStatus(StrEnum):
    STORED = "STORED"
    READY = "READY"
    FAILED = "FAILED"


class KnowledgeBase(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: UUID = Field(default_factory=uuid4)
    key: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1)
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    created_at: datetime = Field(default_factory=utc_now)


class KnowledgeDocument(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: UUID = Field(default_factory=uuid4)
    knowledge_base_key: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    media_type: str = "text/plain"
    source_uri: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: KnowledgeDocumentStatus = KnowledgeDocumentStatus.STORED
    created_at: datetime = Field(default_factory=utc_now)


class KnowledgeChunk(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    ordinal: int = Field(ge=0)
    content: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


DEFAULT_KNOWLEDGE_BASES = (
    ("reference-offers", "Reference Offers", "Approved historical proposals reusable as references."),
    ("architecture-references", "Architecture References", "Architecture patterns, ADRs, standards and technical guidance."),
    ("corporate-roles", "Corporate Roles", "Corporate roles and professional profiles."),
    ("corporate-capabilities", "Corporate Capabilities", "Organizational capabilities and delivery areas."),
    ("accelerators", "Accelerators", "Reusable assets, frameworks and accelerators."),
    ("case-studies", "Case Studies", "Approved case studies and customer success references."),
)
