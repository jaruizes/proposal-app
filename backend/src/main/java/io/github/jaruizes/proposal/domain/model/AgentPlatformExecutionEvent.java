package io.github.jaruizes.proposal.domain.model;

import java.util.Map;
import java.util.UUID;

/** Terminal execution event emitted by the Agent Platform transport. */
public record AgentPlatformExecutionEvent(
        UUID executionId,
        UUID offerId,
        PhaseType phase,
        boolean completed,
        String content,
        String model,
        long inputTokens,
        long outputTokens,
        String providerRequestId,
        String errorMessage,
        Map<String,Object> telemetry) {

    public AgentPlatformExecutionEvent(UUID executionId,UUID offerId,PhaseType phase,boolean completed,
                                       String content,String model,long inputTokens,long outputTokens,
                                       String providerRequestId,String errorMessage) {
        this(executionId,offerId,phase,completed,content,model,inputTokens,outputTokens,
                providerRequestId,errorMessage,Map.of());
    }
}
