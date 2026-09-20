from __future__ import annotations

from typing import Any

KB_DOCUMENT_TYPES = {
    "reference-offers": "REFERENCE_PROPOSAL",
    "architecture-references": "ARCHITECTURE_REFERENCE",
    "corporate-roles": "CORPORATE_ROLE",
    "corporate-capabilities": "CORPORATE_CAPABILITY",
    "accelerators": "ACCELERATOR",
    "case-studies": "CASE_STUDY",
}

class DeterministicKnowledgeClassifier:
    VERSION = "deterministic-kb-v1"

    def classify(self, knowledge_base_key: str, metadata: dict[str, Any]) -> dict[str, Any]:
        existing = metadata.get("classification")
        classification = dict(existing) if isinstance(existing, dict) else {}
        classification.setdefault("document_type", KB_DOCUMENT_TYPES.get(knowledge_base_key, "GENERAL_REFERENCE"))
        classification.setdefault("knowledge_base", knowledge_base_key)
        classification.setdefault("source", "human-selected-knowledge-base")
        classification["version"] = self.VERSION
        for key in ("customer", "sector", "year", "proposal_type", "role", "capability", "technology"):
            value = metadata.get(key)
            if value not in (None, "", []):
                classification.setdefault(key, value)
        tags = metadata.get("tags")
        if isinstance(tags, str):
            tags = [item.strip() for item in tags.split(",") if item.strip()]
        if isinstance(tags, list) and tags:
            classification.setdefault("tags", tags)
        return classification

__all__ = ["DeterministicKnowledgeClassifier", "KB_DOCUMENT_TYPES"]
