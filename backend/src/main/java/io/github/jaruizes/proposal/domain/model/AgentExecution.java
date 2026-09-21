package io.github.jaruizes.proposal.domain.model;
import java.time.Instant; import java.util.Map; import java.util.UUID;

public record AgentExecution(
        UUID id, UUID offerId, PhaseType phase, String agentKey, AgentTaskStatus status,
        String objective, String output, String model, long inputTokens, long outputTokens,
        String providerRequestId, Instant startedAt, Instant completedAt, String errorMessage,
        String checkpointKey, String inputFingerprint, UUID reusedFromExecutionId,
        Map<String,Object> telemetry) {

    public AgentExecution(UUID id, UUID offerId, PhaseType phase, String agentKey, AgentTaskStatus status,
                          String objective, String output, String model, long inputTokens, long outputTokens,
                          String providerRequestId, Instant startedAt, Instant completedAt, String errorMessage,
                          String checkpointKey, String inputFingerprint, UUID reusedFromExecutionId) {
        this(id,offerId,phase,agentKey,status,objective,output,model,inputTokens,outputTokens,
                providerRequestId,startedAt,completedAt,errorMessage,checkpointKey,inputFingerprint,
                reusedFromExecutionId,Map.of());
    }

    public AgentExecution(UUID id, UUID offerId, PhaseType phase, String agentKey, AgentTaskStatus status,
                          String objective, String output, String model, long inputTokens, long outputTokens,
                          String providerRequestId, Instant startedAt, Instant completedAt, String errorMessage) {
        this(id,offerId,phase,agentKey,status,objective,output,model,inputTokens,outputTokens,
                providerRequestId,startedAt,completedAt,errorMessage,null,null,null,Map.of());
    }
}
