package io.github.jaruizes.proposal.domain.model;
import java.time.Instant; import java.util.UUID;

public record PhaseExecution(
        UUID id, UUID offerId, PhaseType phase, ExecutionStatus status, int version,
        String errorMessage, Instant startedAt, Instant completedAt, String refinement) {

    public PhaseExecution(UUID id, UUID offerId, PhaseType phase, ExecutionStatus status, int version,
                          String errorMessage, Instant startedAt, Instant completedAt) {
        this(id,offerId,phase,status,version,errorMessage,startedAt,completedAt,null);
    }
}
