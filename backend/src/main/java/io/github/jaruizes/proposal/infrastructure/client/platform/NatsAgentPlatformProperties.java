package io.github.jaruizes.proposal.infrastructure.client.platform;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

@ConfigurationProperties(prefix = "agent-platform.nats")
public record NatsAgentPlatformProperties(
        String url,
        String commandSubject,
        String eventsSubject,
        String eventsDurable) {

    /** Compatibility constructor for tests/configuration created before event-driven NATS. */
    public NatsAgentPlatformProperties(String url,String commandSubject,String eventsSubject,String eventsDurable,Duration ignoredExecutionTimeout) {
        this(url,commandSubject,eventsSubject,eventsDurable);
    }

    public NatsAgentPlatformProperties {
        if (url == null || url.isBlank()) url = "nats://localhost:4222";
        if (commandSubject == null || commandSubject.isBlank()) commandSubject = "agent-platform.commands.execution.requested";
        if (eventsSubject == null || eventsSubject.isBlank()) eventsSubject = "agent-platform.events.execution.*";
        if (eventsDurable == null || eventsDurable.isBlank()) eventsDurable = "proposal-backend-events";
    }
}
