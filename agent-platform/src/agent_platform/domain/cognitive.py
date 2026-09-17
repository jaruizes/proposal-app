from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CognitiveSection(StrEnum):
    BUSINESS_CONTEXT = "business_context"
    SOURCE_MATERIAL = "source_material"
    PRIOR_ARTIFACT = "prior_artifact"
    MEMORY = "memory"
    RETRIEVED_KNOWLEDGE = "retrieved_knowledge"
    DECISION = "decision"
    REFERENCE = "reference"
    TOOL_CONTEXT = "tool_context"


class EpistemicLabel(StrEnum):
    FACT = "FACT"
    INFERENCE = "INFERENCE"
    ASSUMPTION = "ASSUMPTION"
    QUESTION = "QUESTION"
    DECISION = "DECISION"
    PROPOSAL = "PROPOSAL"
    PRINCIPLE = "PRINCIPLE"
    REFERENCE = "REFERENCE"
    UNCLASSIFIED = "UNCLASSIFIED"


class CognitiveContextItem(BaseModel):
    """One bounded, attributable piece of context supplied to an agent execution."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(min_length=1)
    section: CognitiveSection
    content: Any
    label: EpistemicLabel = EpistemicLabel.UNCLASSIFIED
    source: str = Field(min_length=1)
    priority: int = Field(default=50, ge=0, le=100)
    required: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class CognitiveContext(BaseModel):
    """Provider-neutral context envelope consumed by the runtime and future cognitive services."""

    model_config = ConfigDict(frozen=True)

    items: list[CognitiveContextItem] = Field(default_factory=list)
    knowledge_sources: list[str] = Field(default_factory=list)
    knowledge_scopes: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    dropped_items: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def by_section(self, section: CognitiveSection) -> list[CognitiveContextItem]:
        return [item for item in self.items if item.section is section]

    def summary(self) -> dict[str, Any]:
        counts = {section.value: len(self.by_section(section)) for section in CognitiveSection}
        return {
            "items": len(self.items),
            "sections": counts,
            "knowledge_sources": self.knowledge_sources,
            "knowledge_scopes": self.knowledge_scopes,
            "allowed_tools": self.allowed_tools,
            "warnings": self.warnings,
            "dropped_items": self.dropped_items,
        }
