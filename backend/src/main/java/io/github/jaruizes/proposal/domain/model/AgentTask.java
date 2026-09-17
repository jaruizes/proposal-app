package io.github.jaruizes.proposal.domain.model;

import java.util.Map;
import java.util.UUID;

public record AgentTask(
        UUID id,
        UUID offerId,
        PhaseType phase,
        String agentKey,
        String skillKey,
        String objective,
        String prompt,
        Map<String,Object> metadata) {

    public static AgentTask of(UUID offerId, PhaseType phase, String agentKey, String skillKey, String objective, String prompt) {
        return new AgentTask(UUID.randomUUID(), offerId, phase, agentKey, skillKey, objective, prompt, Map.of());
    }

    public static AgentTask of(UUID offerId, PhaseType phase, String agentKey, String objective, String prompt) {
        return of(offerId, phase, agentKey, null, objective, prompt);
    }
}
