package io.github.jaruizes.proposal.domain.model;
import java.util.Map; import java.util.UUID;
public record AgentTask(UUID id, UUID offerId, PhaseType phase, String agentKey, String objective, String prompt, Map<String,Object> metadata) {
    public static AgentTask of(UUID offerId, PhaseType phase, String agentKey, String objective, String prompt) { return new AgentTask(UUID.randomUUID(), offerId, phase, agentKey, objective, prompt, Map.of()); }
}
