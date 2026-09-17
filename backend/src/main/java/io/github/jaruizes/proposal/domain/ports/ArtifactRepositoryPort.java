package io.github.jaruizes.proposal.domain.ports;

import io.github.jaruizes.proposal.domain.model.Artifact;
import io.github.jaruizes.proposal.domain.model.ArtifactType;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface ArtifactRepositoryPort {
    Artifact save(Artifact artifact);

    List<Artifact> findByOfferId(UUID offerId);

    Optional<Artifact> findLatest(UUID offerId, ArtifactType type);

    int nextVersion(UUID offerId, ArtifactType type);
}
