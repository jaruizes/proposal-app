package io.github.jaruizes.proposal.infrastructure.persistence;

import io.github.jaruizes.proposal.domain.model.Artifact;
import io.github.jaruizes.proposal.domain.model.ArtifactType;
import io.github.jaruizes.proposal.domain.ports.ArtifactRepositoryPort;
import io.github.jaruizes.proposal.infrastructure.persistence.repository.SpringArtifactRepository;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Component
public class ArtifactPersistenceAdapter implements ArtifactRepositoryPort {

    private final SpringArtifactRepository repository;

    public ArtifactPersistenceAdapter(SpringArtifactRepository repository) {
        this.repository = repository;
    }

    @Override
    public Artifact save(Artifact artifact) {
        return PersistenceMapper.toDomain(repository.save(PersistenceMapper.toEntity(artifact)));
    }

    @Override
    public List<Artifact> findByOfferId(UUID offerId) {
        return repository.findByOfferIdOrderByCreatedAtAsc(offerId).stream().map(PersistenceMapper::toDomain).toList();
    }

    @Override
    public Optional<Artifact> findLatest(UUID offerId, ArtifactType type) {
        return repository.findFirstByOfferIdAndTypeOrderByVersionDesc(offerId, type.name()).map(PersistenceMapper::toDomain);
    }

    @Override
    public int nextVersion(UUID offerId, ArtifactType type) {
        return (int) repository.countByOfferIdAndType(offerId, type.name()) + 1;
    }
}
