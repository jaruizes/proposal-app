package io.github.jaruizes.proposal.infrastructure.persistence;

import io.github.jaruizes.proposal.domain.model.PhaseExecution;
import io.github.jaruizes.proposal.domain.model.PhaseType;
import io.github.jaruizes.proposal.domain.ports.PhaseRepositoryPort;
import io.github.jaruizes.proposal.infrastructure.persistence.repository.SpringPhaseRepository;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Component
public class PhasePersistenceAdapter implements PhaseRepositoryPort {

    private final SpringPhaseRepository repository;

    public PhasePersistenceAdapter(SpringPhaseRepository repository) {
        this.repository = repository;
    }

    @Override
    public PhaseExecution save(PhaseExecution phase) {
        return PersistenceMapper.toDomain(repository.save(PersistenceMapper.toEntity(phase)));
    }

    @Override
    public Optional<PhaseExecution> find(UUID offerId, PhaseType phase) {
        return repository.findByOfferIdAndPhase(offerId, phase.name()).map(PersistenceMapper::toDomain);
    }

    @Override
    public List<PhaseExecution> findByOfferId(UUID offerId) {
        return repository.findByOfferId(offerId).stream().map(PersistenceMapper::toDomain).toList();
    }
}
