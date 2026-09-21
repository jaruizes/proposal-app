package io.github.jaruizes.proposal.domain.model;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Versioned, process-agnostic protocol between the business application and Agent Platform.
 *
 * The transport knows executions, inputs/resources, artifacts, usage and errors only.
 * Business semantics stay in agent/skill definitions and in artifact content/metadata.
 */
public final class AgentExecutionProtocol {
    private AgentExecutionProtocol() {}

    public static final String SCHEMA_VERSION = "1";
    public static final String COMMAND_MESSAGE_TYPE = "agent.execution.command";
    public static final String EVENT_MESSAGE_TYPE = "agent.execution.event";

    public record CommandEnvelope(
            @JsonProperty("schema_version") String schemaVersion,
            @JsonProperty("message_type") String messageType,
            String application,
            @JsonProperty("execution_id") UUID executionId,
            Request request) {}

    public record Request(
            @JsonProperty("execution_id") UUID executionId,
            @JsonProperty("correlation_id") UUID correlationId,
            @JsonProperty("agent_key") String agentKey,
            @JsonProperty("skill_key") String skillKey,
            String objective,
            String model,
            Map<String,Object> context,
            Map<String,Object> constraints,
            List<InputResource> attachments) {}

    /**
     * A resource can be inline only when small, or referenced by URI for large/binary content.
     * NATS should carry descriptors/references, not large payloads.
     */
    public record InputResource(
            String name,
            @JsonProperty("media_type") String mediaType,
            String content,
            String uri,
            Map<String,Object> metadata) {}

    public record EventEnvelope(
            @JsonProperty("schema_version") String schemaVersion,
            @JsonProperty("message_type") String messageType,
            @JsonProperty("execution_id") UUID executionId,
            @JsonProperty("event_type") String eventType,
            @JsonProperty("source_event_type") String sourceEventType,
            Map<String,Object> payload) {}

    public record Artifact(
            String type,
            String name,
            @JsonProperty("media_type") String mediaType,
            String content,
            String uri,
            Map<String,Object> metadata) {}

    public record Usage(
            @JsonProperty("input_tokens") long inputTokens,
            @JsonProperty("output_tokens") long outputTokens,
            @JsonProperty("cache_read_tokens") long cacheReadTokens,
            @JsonProperty("cache_write_tokens") long cacheWriteTokens) {}

    public record Error(
            String code,
            String message,
            boolean retryable,
            Map<String,Object> details) {}
}
