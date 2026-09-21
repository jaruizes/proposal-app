package io.github.jaruizes.proposal.infrastructure.client.platform;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.jaruizes.proposal.domain.exceptions.DomainException;
import io.github.jaruizes.proposal.domain.model.AgentPlatformExecutionEvent;
import io.github.jaruizes.proposal.domain.model.AgentTask;
import io.github.jaruizes.proposal.domain.model.LlmRequest;
import io.github.jaruizes.proposal.domain.model.LlmResult;
import io.github.jaruizes.proposal.domain.ports.AsyncAgentPlatformPort;
import io.nats.client.*;
import io.nats.client.api.PublishAck;
import io.nats.client.impl.Headers;
import jakarta.annotation.PreDestroy;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * True command/event transport. submit() only publishes the command; terminal events are
 * emitted into Spring and handled independently by the workflow. No caller waits for the
 * Agent Platform execution lifetime.
 */
@Component
@ConditionalOnProperty(name = "agent-platform.transport", havingValue = "nats", matchIfMissing = true)
public class NatsAgentPlatformAdapter implements AsyncAgentPlatformPort {
    private final NatsAgentPlatformProperties properties;
    private final ObjectMapper mapper;
    private final ApplicationEventPublisher events;
    private final Connection connection;
    private final JetStream jetStream;
    private final JetStreamSubscription subscription;
    private final ExecutorService consumer;
    private volatile boolean running = true;

    public NatsAgentPlatformAdapter(NatsAgentPlatformProperties properties,
                                    ObjectMapper mapper,
                                    ApplicationEventPublisher events) throws Exception {
        this.properties = properties;
        this.mapper = mapper;
        this.events = events;
        this.connection = Nats.connect(properties.url());
        this.jetStream = connection.jetStream();
        var options = PullSubscribeOptions.builder().durable(properties.eventsDurable()).build();
        this.subscription = jetStream.subscribe(properties.eventsSubject(), options);
        this.consumer = Executors.newSingleThreadExecutor(Thread.ofVirtual().name("agent-platform-events-", 0).factory());
        this.consumer.submit(this::consumeLoop);
    }

    @Override
    public void submit(AgentTask task, String model, String context, List<LlmRequest.Attachment> attachments) {
        try {
            var executionId = task.id().toString();
            var request = new LinkedHashMap<String,Object>();
            request.put("execution_id", executionId);
            request.put("correlation_id", task.offerId().toString());
            request.put("agent_key", task.agentKey());
            request.put("skill_key", task.skillKey());
            request.put("objective", task.prompt() == null || task.prompt().isBlank() ? task.objective() : task.prompt());
            request.put("model", model);
            request.put("context", Map.of(
                    "offer_id", task.offerId().toString(),
                    "phase", task.phase().name(),
                    "business_context", context,
                    "spring_objective", task.objective()
            ));
            request.put("constraints", Map.of(
                    "workflow_owner", "spring",
                    "business_phase", task.phase().name(),
                    "commercial_estimation_allowed", false,
                    "output_format", task.metadata().getOrDefault("output_format", "text")
            ));
            request.put("attachments", attachments.stream().map(a -> Map.of(
                    "name", a.name(), "media_type", a.mediaType(), "content", "",
                    "metadata", Map.of("visual_attachment", true, "source", "spring", "base64_omitted", true)
            )).toList());

            var envelope = Map.of(
                    "schema_version", "1",
                    "application", "proposal-copilot",
                    "execution_id", executionId,
                    "request", request
            );
            var headers = new Headers();
            headers.add("Nats-Msg-Id", executionId);
            PublishAck ack = jetStream.publish(properties.commandSubject(), headers, mapper.writeValueAsBytes(envelope));
            if (ack == null) throw new DomainException("NATS did not acknowledge execution command");
        } catch (DomainException e) {
            throw e;
        } catch (Exception e) {
            throw new DomainException("NATS Agent Platform command publish failed: " + e.getMessage());
        }
    }

    /**
     * Synchronous execution is intentionally unsupported for the NATS transport.
     * AgentRuntimeService detects AsyncAgentPlatformPort and uses submit().
     */
    @Override
    public LlmResult execute(AgentTask task, String model, String context, List<LlmRequest.Attachment> attachments) {
        throw new DomainException("NATS Agent Platform transport is asynchronous; use submit()");
    }

    private void consumeLoop() {
        while (running) {
            try {
                for (Message message : subscription.fetch(20, Duration.ofSeconds(1))) {
                    try {
                        var event = mapper.readTree(message.getData());
                        var eventType = event.path("event_type").asText();
                        if ("execution.completed".equals(eventType) || "execution.failed".equals(eventType)) {
                            publishTerminalEvent(event, eventType);
                        }
                        message.ack();
                    } catch (Exception e) {
                        message.nak();
                    }
                }
            } catch (Exception ignored) {
                try { Thread.sleep(500); }
                catch (InterruptedException e) { Thread.currentThread().interrupt(); return; }
            }
        }
    }

    private void publishTerminalEvent(JsonNode event, String eventType) {
        var executionIdText = event.path("execution_id").asText();
        if (executionIdText == null || executionIdText.isBlank()) return;
        var payload = event.path("payload");
        var artifacts = payload.path("artifacts");
        var hasArtifact = artifacts.isArray() && !artifacts.isEmpty()
                && !artifacts.get(0).path("content").asText("").isBlank();
        var completed = "execution.completed".equals(eventType)
                && !"FAILED".equals(payload.path("status").asText())
                && hasArtifact;
        var content = hasArtifact ? artifacts.get(0).path("content").asText() : null;
        var usage = payload.path("usage");
        Map<String,Object> telemetry=Map.of();
        if(hasArtifact){
            var modelMetadata=artifacts.get(0).path("metadata").path("model_metadata");
            if(modelMetadata.isObject()) telemetry=mapper.convertValue(modelMetadata,new TypeReference<Map<String,Object>>(){});
        }
        var error = completed ? null
                : ("execution.failed".equals(eventType)
                    ? payload.path("error").path("message").asText("Agent Platform execution failed")
                    : "Agent Platform completed without a usable artifact");

        events.publishEvent(new AgentPlatformExecutionEvent(
                UUID.fromString(executionIdText),
                null,
                null,
                completed,
                content,
                payload.path("model").asText(null),
                usage.path("input_tokens").asLong(0),
                usage.path("output_tokens").asLong(0),
                nullIfBlank(payload.path("provider_request_id").asText()),
                error,
                telemetry
        ));
    }

    @PreDestroy
    void close() {
        running = false;
        consumer.shutdownNow();
        try { subscription.unsubscribe(); } catch (Exception ignored) {}
        try { connection.close(); } catch (Exception ignored) {}
    }

    private static String nullIfBlank(String value) {
        return value == null || value.isBlank() ? null : value;
    }
}
