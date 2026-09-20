package io.github.jaruizes.proposal.domain.model;

import java.time.Instant;
import java.util.UUID;

public record MaterializedDocument(
        UUID id,
        UUID offerId,
        UUID sourceArtifactId,
        ArtifactType type,
        int contentVersion,
        int renderVersion,
        String mediaType,
        String fileName,
        String templateId,
        String rendererVersion,
        String sourceHash,
        String renderKey,
        DocumentMaterializationStatus status,
        String errorMessage,
        byte[] content,
        Instant createdAt,
        Instant updatedAt) {}
