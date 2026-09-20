package io.github.jaruizes.proposal.domain.ports;

import io.github.jaruizes.proposal.domain.model.ArtifactType;
import io.github.jaruizes.proposal.domain.model.MaterializedDocument;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface MaterializedDocumentRepositoryPort {
    MaterializedDocument save(MaterializedDocument document);
    List<MaterializedDocument> findByOfferId(UUID offerId);
    Optional<MaterializedDocument> findById(UUID id);
    Optional<MaterializedDocument> findByRenderKey(String renderKey);
    int nextRenderVersion(UUID offerId, ArtifactType type);
}
