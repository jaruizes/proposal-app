package io.github.jaruizes.proposal.domain.model;

import java.util.LinkedHashMap;
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
        return new AgentTask(UUID.randomUUID(), offerId, phase, agentKey, skillKey, objective, prompt, Map.of("output_format", "markdown"));
    }

    public AgentTask withOutputFormat(String format) {
        var next=new LinkedHashMap<String,Object>(metadata);
        next.put("output_format",format);
        return new AgentTask(id, offerId, phase, agentKey, skillKey, objective, prompt, Map.copyOf(next));
    }

    public AgentTask withCheckpoint(String checkpointKey) {
        var next=new LinkedHashMap<String,Object>(metadata);
        next.put("checkpoint_key",checkpointKey);
        return new AgentTask(id, offerId, phase, agentKey, skillKey, objective, prompt, Map.copyOf(next));
    }

    public String checkpointKey() {
        return String.valueOf(metadata.getOrDefault("checkpoint_key",""));
    }

    public static AgentTask of(UUID offerId, PhaseType phase, String agentKey, String objective, String prompt) {
        return of(offerId, phase, agentKey, null, objective, prompt);
    }
}
