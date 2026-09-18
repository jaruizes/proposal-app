from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RetrievalMode(StrEnum):
    VECTOR = "vector"
    KEYWORD = "keyword"
    GRAPH = "graph"
    HYBRID = "hybrid"


class RetrievalFilters(BaseModel):
    model_config = ConfigDict(frozen=True)

    knowledge_base_keys: list[str] = Field(default_factory=list)
    document_ids: list[UUID] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    document_metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1)
    mode: RetrievalMode = RetrievalMode.HYBRID
    top_k: int = Field(default=5, ge=1, le=50)
    candidate_k: int = Field(default=20, ge=1, le=200)
    filters: RetrievalFilters = Field(default_factory=RetrievalFilters)
    expand_parents: bool = True
    vector_weight: float = Field(default=1.0, gt=0)
    keyword_weight: float = Field(default=1.0, gt=0)
    ontology_enabled: bool = True
    ontology_weight: float = Field(default=1.0, gt=0)
    ontology_max_hops: int = Field(default=1, ge=0, le=3)
    ontology_max_concepts: int = Field(default=12, ge=1, le=50)


class RetrievalHit(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk_id: UUID
    document_id: UUID
    knowledge_base_key: str
    title: str
    content: str
    score: float
    retrieval_method: RetrievalMode
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_uri: str | None = None
    parent_chunk_id: UUID | None = None
    parent_content: str | None = None
    parent_metadata: dict[str, Any] | None = None


class RetrievalResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    query: str
    mode: RetrievalMode
    hits: list[RetrievalHit] = Field(default_factory=list)
    embedding_model: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
