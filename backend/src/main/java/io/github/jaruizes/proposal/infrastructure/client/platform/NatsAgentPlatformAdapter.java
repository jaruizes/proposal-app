package io.github.jaruizes.proposal.infrastructure.client.platform;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.jaruizes.proposal.domain.exceptions.DomainException;
import io.github.jaruizes.proposal.domain.model.AgentTask;
import io.github.jaruizes.proposal.domain.model.LlmRequest;
import io.github.jaruizes.proposal.domain.model.LlmResult;
import io.github.jaruizes.proposal.domain.ports.AgentPlatformPort;
import io.nats.client.*;
import io.nats.client.api.ConsumerConfiguration;
import io.nats.client.api.DeliverPolicy;
import io.nats.client.api.PublishAck;
import io.nats.client.impl.Headers;
import jakarta.annotation.PreDestroy;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;

@Component
@ConditionalOnProperty(name = "agent-platform.transport", havingValue = "nats", matchIfMissing = true)
public class NatsAgentPlatformAdapter implements AgentPlatformPort {
    private final NatsAgentPlatformProperties properties;
    private final ObjectMapper mapper;
    private final Connection connection;
    private final JetStream jetStream;
    private final JetStreamSubscription subscription;
    private final ExecutorService consumer;
    private final ConcurrentMap<String, CompletableFuture<JsonNode>> pending = new ConcurrentHashMap<>();
    private volatile boolean running = true;

    public NatsAgentPlatformAdapter(NatsAgentPlatformProperties properties, ObjectMapper mapper) throws Exception {
        this.properties = properties;
        this.mapper = mapper;
        this.connection = Nats.connect(properties.url());
        this.jetStream = connection.jetStream();
        var options = PullSubscribeOptions.builder().durable(properties.eventsDurable()).build();
        this.subscription = jetStream.subscribe(properties.eventsSubject(), options);
        this.consumer = Executors.newSingleThreadExecutor(Thread.ofVirtual().name("agent-platform-events-", 0).factory());
        this.consumer.submit(this::consumeLoop);
    }

    @Override
    public LlmResult execute(AgentTask task, String model, String context, List<LlmRequest.Attachment> attachments) {
        var executionId = task.id().toString();
        var future = new CompletableFuture<JsonNode>();
        if (pending.putIfAbsent(executionId, future) != null) {
            throw new DomainException("Execution already pending: " + executionId);
        }

        try {
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
                    "commercial_estimation_allowed", false
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

            JsonNode event = future.get(properties.executionTimeout().toMillis(), TimeUnit.MILLISECONDS);
            var payload = event.path("payload");
            if ("FAILED".equals(payload.path("status").asText()) || event.path("event_type").asText().equals("execution.failed")) {
                throw new DomainException(payload.path("error").path("message").asText("Agent Platform execution failed"));
            }
            var artifacts = payload.path("artifacts");
            if (!artifacts.isArray() || artifacts.isEmpty()) throw new DomainException("Agent Platform returned no artifact");
            var usage = payload.path("usage");
            return new LlmResult(
                    artifacts.get(0).path("content").asText(),
                    payload.path("model").asText(model),
                    usage.path("input_tokens").asLong(0),
                    usage.path("output_tokens").asLong(0),
                    nullIfBlank(payload.path("provider_request_id").asText())
            );
        } catch (TimeoutException e) {
            throw new DomainException("Agent Platform execution timed out after " + properties.executionTimeout());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new DomainException("Interrupted while waiting for Agent Platform event");
        } catch (ExecutionException e) {
            throw new DomainException(e.getCause() == null ? e.getMessage() : e.getCause().getMessage());
        } catch (DomainException e) {
            throw e;
        } catch (Exception e) {
            throw new DomainException("NATS Agent Platform transport failed: " + e.getMessage());
        } finally {
            pending.remove(executionId);
        }
    }

    private void consumeLoop() {
        while (running) {
            try {
                for (Message message : subscription.fetch(20, Duration.ofSeconds(1))) {
                    try {
                        var event = mapper.readTree(message.getData());
                        var executionId = event.path("execution_id").asText();
                        var eventType = event.path("event_type").asText();
                        if ("execution.completed".equals(eventType) || "execution.failed".equals(eventType)) {
                            var future = pending.get(executionId);
                            if (future != null) future.complete(event);
                        }
                        message.ack();
                    } catch (Exception e) {
                        message.nak();
                    }
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return;
            } catch (Exception ignored) {
                try { Thread.sleep(500); } catch (InterruptedException e) { Thread.currentThread().interrupt(); return; }
            }
        }
    }

    @PreDestroy
    void close() {
        running = false;
        consumer.shutdownNow();
        try { subscription.unsubscribe(); } catch (Exception ignored) {}
        try { connection.close(); } catch (Exception ignored) {}
    }

    private static String nullIfBlank(String value) { return value == null || value.isBlank() ? null : value; }
}
