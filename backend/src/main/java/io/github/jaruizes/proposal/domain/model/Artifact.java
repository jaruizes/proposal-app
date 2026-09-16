package io.github.jaruizes.proposal.domain.model;
import java.time.Instant; import java.util.UUID;
public record Artifact(UUID id, UUID offerId, PhaseType phase, ArtifactType type, int version, String content, Instant createdAt) {}
