package io.github.jaruizes.proposal.business;

import io.github.jaruizes.proposal.domain.model.ExecutionStatus;
import io.github.jaruizes.proposal.domain.model.PhaseExecution;
import io.github.jaruizes.proposal.domain.model.PhaseType;
import io.github.jaruizes.proposal.domain.ports.PhaseRepositoryPort;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.UUID;

@Service
public class SourceChangeInvalidationService {

    private final PhaseRepositoryPort phases;

    public SourceChangeInvalidationService(PhaseRepositoryPort phases) {
        this.phases = phases;
    }

    public void invalidateForSourceChange(UUID offerId, String previousHash, String currentHash) {
        var reason = "Source corpus changed: %s -> %s".formatted(shortHash(previousHash), shortHash(currentHash));
        var now = Instant.now();

        for (var phase : phases.findByOfferId(offerId)) {
            var status = phase.phase() == PhaseType.ANALYSIS
                    ? ExecutionStatus.INVALIDATED
                    : ExecutionStatus.STALE;

            phases.save(new PhaseExecution(
                    phase.id(),
                    phase.offerId(),
                    phase.phase(),
                    status,
                    phase.version(),
                    reason,
                    phase.startedAt(),
                    now));
        }
    }

    private static String shortHash(String hash) {
        if (hash == null || hash.isBlank()) return "unknown";
        return hash.length() <= 12 ? hash : hash.substring(0, 12);
    }
}
