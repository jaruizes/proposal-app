package io.github.jaruizes.proposal.domain.model;
import java.time.Instant; import java.util.UUID;
public record AgentExecution(UUID id, UUID offerId, PhaseType phase, String agentKey, AgentTaskStatus status, String objective, String output, String model, long inputTokens, long outputTokens, String providerRequestId, Instant startedAt, Instant completedAt, String errorMessage) {}
