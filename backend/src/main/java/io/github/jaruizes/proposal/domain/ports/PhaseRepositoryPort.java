package io.github.jaruizes.proposal.domain.ports;
import io.github.jaruizes.proposal.domain.model.*; import java.util.*;
public interface PhaseRepositoryPort { PhaseExecution save(PhaseExecution phase); Optional<PhaseExecution> find(UUID offerId, PhaseType phase); List<PhaseExecution> findByOfferId(UUID offerId); }
