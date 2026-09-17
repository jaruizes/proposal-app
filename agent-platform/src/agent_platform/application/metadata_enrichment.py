from __future__ import annotations

import hashlib
import re
from collections import Counter
from enum import StrEnum
from typing import Protocol

from agent_platform.domain import KnowledgeChunk, KnowledgeDocument


class MetadataEnrichmentProfile(StrEnum):
    NONE = "none"
    BASIC = "basic"
    STANDARD = "standard"


class MetadataEnricher(Protocol):
    async def enrich_document(
        self,
        document: KnowledgeDocument,
        content: str,
        *,
        profile: MetadataEnrichmentProfile,
        max_keywords: int,
    ) -> dict: ...

    async def enrich_chunk(
        self,
        document: KnowledgeDocument,
        chunk: KnowledgeChunk,
        *,
        profile: MetadataEnrichmentProfile,
        max_keywords: int,
        document_enrichment: dict,
    ) -> dict: ...


class DeterministicMetadataEnricher:
    """Cheap, deterministic enrichment that requires no model call or external service."""

    VERSION = "deterministic-v1"
    _TOKEN = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9][A-Za-zÀ-ÖØ-öø-ÿ0-9_-]{1,}", re.UNICODE)
    _HEADING = re.compile(r"(?m)^(#{1,6})\s+(.+?)\s*$")
    _STOPWORDS = {
        "en": {
            "the", "and", "for", "with", "that", "this", "from", "into", "are", "was", "were", "will",
            "have", "has", "had", "not", "but", "can", "our", "your", "their", "about", "using", "use",
            "used", "than", "then", "when", "where", "which", "who", "what", "how", "all", "any", "each",
            "its", "also", "such", "these", "those", "been", "being", "would", "should", "could", "must",
        },
        "es": {
            "que", "los", "las", "del", "por", "para", "con", "una", "uno", "unos", "unas", "como", "más",
            "pero", "sus", "este", "esta", "estos", "estas", "entre", "desde", "sobre", "cuando", "donde",
            "todo", "toda", "todos", "todas", "también", "ser", "son", "fue", "han", "hay", "sin", "cada",
            "se", "al", "lo", "un", "y", "o", "de", "la", "el", "en", "es", "a",
        },
    }

    async def enrich_document(self, document, content, *, profile, max_keywords) -> dict:
        if profile is MetadataEnrichmentProfile.NONE:
            return {}
        language = self._detect_language(content)
        enrichment = self._base(content, language, profile)
        enrichment["media_type"] = document.media_type
        if profile is MetadataEnrichmentProfile.STANDARD:
            enrichment["keywords"] = self._keywords(content, language, max_keywords)
            enrichment["headings"] = [
                {"level": len(match.group(1)), "text": match.group(2).strip()}
                for match in self._HEADING.finditer(content)
            ][:50]
        return enrichment

    async def enrich_chunk(self, document, chunk, *, profile, max_keywords, document_enrichment) -> dict:
        if profile is MetadataEnrichmentProfile.NONE:
            return {}
        language = document_enrichment.get("language") or self._detect_language(chunk.content)
        enrichment = self._base(chunk.content, language, profile)
        enrichment["sentence_count"] = len(re.findall(r"(?<=[.!?])\s+", chunk.content)) + (1 if chunk.content.strip() else 0)
        if profile is MetadataEnrichmentProfile.STANDARD:
            enrichment["keywords"] = self._keywords(chunk.content, language, max_keywords)
            enrichment["document_keywords"] = document_enrichment.get("keywords", [])
        return enrichment

    def _base(self, content: str, language: str, profile: MetadataEnrichmentProfile) -> dict:
        words = self._TOKEN.findall(content)
        return {
            "version": self.VERSION,
            "profile": profile.value,
            "language": language,
            "char_count": len(content),
            "word_count": len(words),
            "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        }

    def _detect_language(self, content: str) -> str:
        tokens = [token.lower() for token in self._TOKEN.findall(content)]
        if not tokens:
            return "undetermined"
        sample = tokens[:2000]
        en = sum(token in self._STOPWORDS["en"] for token in sample)
        es = sum(token in self._STOPWORDS["es"] for token in sample)
        if en == es == 0:
            return "undetermined"
        return "es" if es > en else "en"

    def _keywords(self, content: str, language: str, limit: int) -> list[str]:
        if limit <= 0:
            return []
        stopwords = self._STOPWORDS.get(language, set()) | self._STOPWORDS["en"] | self._STOPWORDS["es"]
        tokens = [token.lower() for token in self._TOKEN.findall(content)]
        candidates = [token for token in tokens if len(token) >= 3 and token not in stopwords and not token.isdigit()]
        counts = Counter(candidates)
        first_position: dict[str, int] = {}
        for index, token in enumerate(candidates):
            first_position.setdefault(token, index)
        ordered = sorted(counts, key=lambda token: (-counts[token], first_position[token], token))
        return ordered[:limit]


__all__ = [
    "DeterministicMetadataEnricher",
    "MetadataEnricher",
    "MetadataEnrichmentProfile",
]
