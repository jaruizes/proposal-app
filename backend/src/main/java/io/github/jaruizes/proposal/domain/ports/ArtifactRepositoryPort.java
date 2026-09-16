package io.github.jaruizes.proposal.domain.ports;
import io.github.jaruizes.proposal.domain.model.*; import java.util.*;
public interface ArtifactRepositoryPort { Artifact save(Artifact artifact); List<Artifact> findByOfferId(UUID offerId); Optional<Artifact> findLatest(UUID offerId, ArtifactType type); int nextVersion(UUID offerId, ArtifactType type); }
