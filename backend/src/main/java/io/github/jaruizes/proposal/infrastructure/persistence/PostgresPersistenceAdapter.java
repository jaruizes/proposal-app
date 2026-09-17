package io.github.jaruizes.proposal.infrastructure.persistence;

import io.github.jaruizes.proposal.domain.model.AgentExecution;
import io.github.jaruizes.proposal.domain.model.Artifact;
import io.github.jaruizes.proposal.domain.model.ArtifactType;
import io.github.jaruizes.proposal.domain.model.Offer;
import io.github.jaruizes.proposal.domain.model.PhaseExecution;
import io.github.jaruizes.proposal.domain.model.PhaseType;
import io.github.jaruizes.proposal.domain.ports.AgentExecutionRepositoryPort;
import io.github.jaruizes.proposal.domain.ports.ArtifactRepositoryPort;
import io.github.jaruizes.proposal.domain.ports.OfferRepositoryPort;
import io.github.jaruizes.proposal.domain.ports.PhaseRepositoryPort;
import io.github.jaruizes.proposal.infrastructure.persistence.repository.SpringAgentExecutionRepository;
import io.github.jaruizes.proposal.infrastructure.persistence.repository.SpringArtifactRepository;
import io.github.jaruizes.proposal.infrastructure.persistence.repository.SpringOfferRepository;
import io.github.jaruizes.proposal.infrastructure.persistence.repository.SpringPhaseRepository;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Component
public class PostgresPersistenceAdapter implements OfferRepositoryPort,
        PhaseRepositoryPort,
        ArtifactRepositoryPort,
        AgentExecutionRepositoryPort {

    private final SpringOfferRepository offers;
    private final SpringPhaseRepository phases;
    private final SpringArtifactRepository artifacts;
    private final SpringAgentExecutionRepository executions;

    public PostgresPersistenceAdapter(SpringOfferRepository offers,
                                      SpringPhaseRepository phases,
                                      SpringArtifactRepository artifacts,
                                      SpringAgentExecutionRepository executions) {
        this.offers = offers;
        this.phases = phases;
        this.artifacts = artifacts;
        this.executions = executions;
    }

    @Override
    public Offer save(Offer offer) {
        return PersistenceMapper.toDomain(offers.save(PersistenceMapper.toEntity(offer)));
    }

    @Override
    public Optional<Offer> findById(UUID id) {
        return offers.findById(id).map(PersistenceMapper::toDomain);
    }

    @Override
    public List<Offer> findAll() {
        return offers.findAll().stream().map(PersistenceMapper::toDomain).toList();
    }

    @Override
    public PhaseExecution save(PhaseExecution phase) {
        return PersistenceMapper.toDomain(phases.save(PersistenceMapper.toEntity(phase)));
    }

    @Override
    public Optional<PhaseExecution> find(UUID offerId, PhaseType phase) {
        return phases.findByOfferIdAndPhase(offerId, phase.name()).map(PersistenceMapper::toDomain);
    }

    @Override
    public List<PhaseExecution> findPhasesByOfferId(UUID offerId) {
        return phases.findByOfferId(offerId).stream().map(PersistenceMapper::toDomain).toList();
    }

    @Override
    public Artifact save(Artifact artifact) {
        return PersistenceMapper.toDomain(artifacts.save(PersistenceMapper.toEntity(artifact)));
    }

    @Override
    public List<Artifact> findArtifactsByOfferId(UUID offerId) {
        return artifacts.findByOfferIdOrderByCreatedAtAsc(offerId).stream().map(PersistenceMapper::toDomain).toList();
    }

    @Override
    public Optional<Artifact> findLatest(UUID offerId, ArtifactType type) {
        return artifacts.findFirstByOfferIdAndTypeOrderByVersionDesc(offerId, type.name()).map(PersistenceMapper::toDomain);
    }

    @Override
    public int nextVersion(UUID offerId, ArtifactType type) {
        return (int) artifacts.countByOfferIdAndType(offerId, type.name()) + 1;
    }

    @Override
    public AgentExecution save(AgentExecution execution) {
        return PersistenceMapper.toDomain(executions.save(PersistenceMapper.toEntity(execution)));
    }

    @Override
    public List<AgentExecution> findAgentExecutionsByOfferId(UUID offerId) {
        return executions.findByOfferIdOrderByStartedAtAsc(offerId).stream().map(PersistenceMapper::toDomain).toList();
    }
}
