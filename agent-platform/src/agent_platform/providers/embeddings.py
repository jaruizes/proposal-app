from __future__ import annotations

import hashlib
import math

from agent_platform.application.embeddings import EmbeddingRequest, EmbeddingResult


class HashEmbeddingProvider:
    """Deterministic local embedding provider for development and integration tests.

    It is intentionally provider-neutral and credential-free. It is NOT intended
    to provide production semantic quality; a real embedding provider can replace
    it without changing the ingestion pipeline.
    """

    def __init__(self, *, dimensions: int = 384, model: str = "hash-embedding-v1") -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be > 0")
        self._dimensions = dimensions
        self._model = model

    @property
    def provider_key(self) -> str:
        return "hash"

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        vectors = [self._embed_text(text) for text in request.texts]
        return EmbeddingResult(vectors=vectors, model=self.model, dimensions=self.dimensions)

    def _embed_text(self, text: str) -> list[float]:
        # Feature hashing over normalized tokens gives deterministic, bounded vectors.
        vector = [0.0] * self.dimensions
        tokens = text.lower().split()
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector
