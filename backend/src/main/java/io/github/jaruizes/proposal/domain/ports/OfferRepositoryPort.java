package io.github.jaruizes.proposal.domain.ports;
import io.github.jaruizes.proposal.domain.model.Offer; import java.util.*;
public interface OfferRepositoryPort { Offer save(Offer offer); Optional<Offer> findById(UUID id); List<Offer> findAll(); }
