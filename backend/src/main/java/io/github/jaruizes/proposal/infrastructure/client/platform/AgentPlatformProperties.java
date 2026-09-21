package io.github.jaruizes.proposal.infrastructure.client.platform;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

@ConfigurationProperties(prefix = "agent-platform")
public record AgentPlatformProperties(
        String baseUrl,
        String apiKey,
        Duration pollInterval,
        Duration executionTimeout,
        Duration proposalExecutionTimeout) {

    public AgentPlatformProperties(String baseUrl,String apiKey,Duration pollInterval,Duration executionTimeout) {
        this(baseUrl,apiKey,pollInterval,executionTimeout,Duration.ofMinutes(30));
    }

    public AgentPlatformProperties {
        if (baseUrl == null || baseUrl.isBlank()) baseUrl = "http://localhost:8000";
        if (pollInterval == null) pollInterval = Duration.ofSeconds(1);
        if (executionTimeout == null) executionTimeout = Duration.ofMinutes(10);
        if (proposalExecutionTimeout == null) proposalExecutionTimeout = Duration.ofMinutes(30);
    }
}
