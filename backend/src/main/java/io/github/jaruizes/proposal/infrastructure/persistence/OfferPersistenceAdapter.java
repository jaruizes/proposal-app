package io.github.jaruizes.proposal.infrastructure.persistence;

import io.github.jaruizes.proposal.domain.model.Offer;
import io.github.jaruizes.proposal.domain.ports.OfferRepositoryPort;
import io.github.jaruizes.proposal.infrastructure.persistence.repository.SpringOfferRepository;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Component
public class OfferPersistenceAdapter implements OfferRepositoryPort {

    private final SpringOfferRepository repository;

    public OfferPersistenceAdapter(SpringOfferRepository repository) {
        this.repository = repository;
    }

    @Override
    public Offer save(Offer offer) {
        return PersistenceMapper.toDomain(repository.save(PersistenceMapper.toEntity(offer)));
    }

    @Override
    public Optional<Offer> findById(UUID id) {
        return repository.findById(id).map(PersistenceMapper::toDomain);
    }

    @Override
    public List<Offer> findAll() {
        return repository.findAll().stream().map(PersistenceMapper::toDomain).toList();
    }
}
