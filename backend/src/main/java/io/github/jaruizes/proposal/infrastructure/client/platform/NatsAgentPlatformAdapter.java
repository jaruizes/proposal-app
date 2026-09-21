package io.github.jaruizes.proposal.infrastructure.client.platform;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.jaruizes.proposal.domain.exceptions.DomainException;
import io.github.jaruizes.proposal.domain.model.AgentPlatformExecutionEvent;
import io.github.jaruizes.proposal.domain.model.AgentExecutionProtocol;
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
            var executionId = task.id();
            var request = new AgentExecutionProtocol.Request(
                    executionId,
                    task.offerId(),
                    task.agentKey(),
                    task.skillKey(),
                    task.prompt() == null || task.prompt().isBlank() ? task.objective() : task.prompt(),
                    model,
                    Map.of(
                            "process_instance_id", task.offerId().toString(),
                            "business_step", task.phase().name(),
                            "business_context", context,
                            "business_objective", task.objective()
                    ),
                    Map.of(
                            "workflow_owner", "spring",
                            "business_step", task.phase().name(),
                            "commercial_estimation_allowed", false,
                            "output_format", task.metadata().getOrDefault("output_format", "text")
                    ),
                    attachments.stream().map(a -> new AgentExecutionProtocol.InputResource(
                            a.name(),
                            a.mediaType(),
                            null,
                            null,
                            Map.of(
                                    "source", "spring",
                                    "inline_binary_omitted", true,
                                    "original_bytes_base64", a.base64Data()==null?0:a.base64Data().length()
                            )
                    )).toList()
            );

            var envelope = new AgentExecutionProtocol.CommandEnvelope(
                    AgentExecutionProtocol.SCHEMA_VERSION,
                    AgentExecutionProtocol.COMMAND_MESSAGE_TYPE,
                    "proposal-copilot",
                    executionId,
                    request
            );
            var payload = mapper.writeValueAsBytes(envelope);
            if (payload.length > properties.maxCommandBytes()) {
                throw new DomainException(
                        "Agent command payload is too large for NATS transport: %d bytes (safe limit %d). "
                        .formatted(payload.length, properties.maxCommandBytes())
                        + "Compact or externalize large documents/binaries and send references instead."
                );
            }
            var headers = new Headers();
            headers.add("Nats-Msg-Id", executionId.toString());
            PublishAck ack = jetStream.publish(properties.commandSubject(), headers, payload);
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
                        var event = mapper.readValue(message.getData(), AgentExecutionProtocol.EventEnvelope.class);
                        var eventType = event.eventType();
                        if ("execution.completed".equals(eventType) || "execution.failed".equals(eventType)) {
                            publishTerminalEvent(event);
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

    private void publishTerminalEvent(AgentExecutionProtocol.EventEnvelope event) {
        var payload = mapper.valueToTree(event.payload());
        var artifactNodes = payload.path("artifacts");
        var artifactList = new java.util.ArrayList<AgentPlatformArtifact>();
        if (artifactNodes.isArray()) {
            for (var artifact : artifactNodes) {
                artifactList.add(new AgentPlatformArtifact(
                        artifact.path("type").asText("AGENT_OUTPUT"),
                        nullIfBlank(artifact.path("name").asText()),
                        artifact.path("media_type").asText("text/plain"),
                        nullIfBlank(artifact.path("content").asText()),
                        nullIfBlank(artifact.path("uri").asText()),
                        artifact.path("metadata").isObject()
                                ? mapper.convertValue(artifact.path("metadata"), new TypeReference<Map<String,Object>>(){})
                                : Map.of()
                ));
            }
        }
        var primary = artifactList.stream()
                .filter(AgentPlatformArtifact::hasInlineContent)
                .findFirst()
                .orElse(null);
        var hasArtifact = artifactList.stream().anyMatch(a -> a.hasInlineContent() || a.hasReference());
        var completed = "execution.completed".equals(event.eventType())
                && !"FAILED".equals(payload.path("status").asText())
                && hasArtifact;
        var content = primary == null ? null : primary.content();
        var usage = payload.path("usage");
        Map<String,Object> telemetry=Map.of();
        if(primary!=null && primary.metadata()!=null){
            var modelMetadata=primary.metadata().get("model_metadata");
            if(modelMetadata instanceof Map<?,?> map){
                @SuppressWarnings("unchecked")
                var cast=(Map<String,Object>)map;
                telemetry=cast;
            }
        }
        var error = completed ? null
                : ("execution.failed".equals(event.eventType())
                    ? payload.path("error").path("message").asText("Agent Platform execution failed")
                    : "Agent Platform completed without a usable artifact");

        events.publishEvent(new AgentPlatformExecutionEvent(
                event.executionId(),
                null,
                null,
                completed,
                content,
                payload.path("model").asText(null),
                usage.path("input_tokens").asLong(0),
                usage.path("output_tokens").asLong(0),
                nullIfBlank(payload.path("provider_request_id").asText()),
                error,
                telemetry,
                List.copyOf(artifactList)
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
