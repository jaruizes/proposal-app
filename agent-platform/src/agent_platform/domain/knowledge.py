from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeDocumentStatus(StrEnum):
    STORED = "STORED"
    PROCESSING = "PROCESSING"
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
    embedding: list[float] | None = None
    embedding_model: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


DEFAULT_KNOWLEDGE_BASES = (
    ("reference-offers", "Ofertas de referencia", "Propuestas históricas aprobadas reutilizables como referencia."),
    ("architecture-references", "Referencias de arquitectura", "Patrones de arquitectura, ADRs, estándares y guías técnicas."),
    ("corporate-roles", "Roles corporativos", "Roles corporativos y perfiles profesionales."),
    ("corporate-capabilities", "Capacidades corporativas", "Capacidades organizativas y áreas de entrega."),
    ("accelerators", "Aceleradores", "Activos reutilizables, frameworks y aceleradores."),
    ("case-studies", "Casos de éxito", "Casos de estudio aprobados y referencias de éxito de clientes."),
)
