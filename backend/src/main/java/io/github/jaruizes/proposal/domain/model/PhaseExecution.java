package io.github.jaruizes.proposal.domain.model;
import java.time.Instant; import java.util.UUID;
public record PhaseExecution(UUID id, UUID offerId, PhaseType phase, ExecutionStatus status, int version, String errorMessage, Instant startedAt, Instant completedAt) {}
