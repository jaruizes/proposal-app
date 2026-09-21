package io.github.jaruizes.proposal.infrastructure.persistence;

import io.github.jaruizes.proposal.domain.model.AgentExecution;
import io.github.jaruizes.proposal.domain.ports.AgentExecutionRepositoryPort;
import io.github.jaruizes.proposal.infrastructure.persistence.repository.SpringAgentExecutionRepository;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.UUID;

@Component
public class AgentExecutionPersistenceAdapter implements AgentExecutionRepositoryPort {

    private final SpringAgentExecutionRepository repository;

    public AgentExecutionPersistenceAdapter(SpringAgentExecutionRepository repository) {
        this.repository = repository;
    }

    @Override
    public AgentExecution save(AgentExecution execution) {
        return PersistenceMapper.toDomain(repository.save(PersistenceMapper.toEntity(execution)));
    }

    @Override
    public List<AgentExecution> findByOfferId(UUID offerId) {
        return repository.findByOfferIdOrderByStartedAtAsc(offerId).stream().map(PersistenceMapper::toDomain).toList();
    }

    @Override
    public java.util.Optional<AgentExecution> findById(UUID id) {
        return repository.findById(id).map(PersistenceMapper::toDomain);
    }
}
