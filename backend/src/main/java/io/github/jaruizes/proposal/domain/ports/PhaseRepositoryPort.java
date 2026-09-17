package io.github.jaruizes.proposal.domain.ports;

import io.github.jaruizes.proposal.domain.model.PhaseExecution;
import io.github.jaruizes.proposal.domain.model.PhaseType;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface PhaseRepositoryPort {
    PhaseExecution save(PhaseExecution phase);

    Optional<PhaseExecution> find(UUID offerId, PhaseType phase);

    List<PhaseExecution> findByOfferId(UUID offerId);
}
