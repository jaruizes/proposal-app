package io.github.jaruizes.proposal.infrastructure.client.platform;

import com.fasterxml.jackson.databind.JsonNode;
import io.github.jaruizes.proposal.domain.exceptions.DomainException;
import io.github.jaruizes.proposal.domain.model.AgentTask;
import io.github.jaruizes.proposal.domain.model.LlmRequest;
import io.github.jaruizes.proposal.domain.model.LlmResult;
import io.github.jaruizes.proposal.domain.ports.AgentPlatformPort;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Instant;
import java.util.*;

@Component
@ConditionalOnProperty(name = "agent-platform.transport", havingValue = "http")
public class HttpAgentPlatformAdapter implements AgentPlatformPort {
    private final AgentPlatformProperties properties;
    private final WebClient client;

    public HttpAgentPlatformAdapter(AgentPlatformProperties properties, WebClient.Builder builder) {
        this.properties = properties;
        var configured = builder.baseUrl(properties.baseUrl());
        if (properties.apiKey() != null && !properties.apiKey().isBlank()) {
            configured.defaultHeader("X-API-Key", properties.apiKey());
        }
        this.client = configured.build();
    }

    @Override
    public LlmResult execute(AgentTask task, String model, String context, List<LlmRequest.Attachment> attachments) {
        var body = new LinkedHashMap<String,Object>();
        body.put("execution_id", task.id().toString());
        body.put("correlation_id", task.offerId().toString());
        body.put("agent_key", task.agentKey());
        body.put("skill_key", task.skillKey());
        body.put("objective", task.prompt() == null || task.prompt().isBlank() ? task.objective() : task.prompt());
        body.put("model", model);
        body.put("context", Map.of(
                "offer_id", task.offerId().toString(),
                "phase", task.phase().name(),
                "business_context", context,
                "spring_objective", task.objective()
        ));
        body.put("constraints", Map.of(
                "workflow_owner", "spring",
                "business_phase", task.phase().name(),
                "commercial_estimation_allowed", false,
                "output_format", task.metadata().getOrDefault("output_format", "text")
        ));
        body.put("attachments", attachments.stream().map(a -> Map.of(
                "name", a.name(),
                "media_type", a.mediaType(),
                "content", "",
                "metadata", Map.of("visual_attachment", true, "source", "spring", "base64_omitted", true)
        )).toList());

        JsonNode submitted = client.post().uri("/v1/executions").contentType(MediaType.APPLICATION_JSON)
                .bodyValue(body).retrieve().bodyToMono(JsonNode.class).block();
        if (submitted == null || submitted.path("id").asText().isBlank()) {
            throw new DomainException("Agent Platform returned an invalid submission response");
        }
        var executionId = submitted.path("id").asText();
        waitForCompletion(executionId);

        JsonNode result = client.get().uri("/v1/executions/{id}/result", executionId)
                .retrieve().bodyToMono(JsonNode.class).block();
        if (result == null) throw new DomainException("Agent Platform returned an empty result");
        if (!"COMPLETED".equals(result.path("status").asText())) {
            throw new DomainException(result.path("error").path("message").asText("Agent Platform execution failed"));
        }
        var artifacts = result.path("artifacts");
        if (!artifacts.isArray() || artifacts.isEmpty()) throw new DomainException("Agent Platform returned no artifact");
        var usage = result.path("usage");
        return new LlmResult(artifacts.get(0).path("content").asText(), result.path("model").asText(model),
                usage.path("input_tokens").asLong(0), usage.path("output_tokens").asLong(0),
                nullIfBlank(result.path("provider_request_id").asText()));
    }

    private void waitForCompletion(String executionId) {
        var deadline = Instant.now().plus(properties.executionTimeout());
        while (Instant.now().isBefore(deadline)) {
            JsonNode execution = client.get().uri("/v1/executions/{id}", executionId)
                    .retrieve().bodyToMono(JsonNode.class).block();
            if (execution == null) throw new DomainException("Agent Platform execution disappeared");
            var status = execution.path("status").asText();
            if ("COMPLETED".equals(status)) return;
            if ("FAILED".equals(status) || "CANCELLED".equals(status)) {
                throw new DomainException(execution.path("error").path("message").asText("Agent Platform execution " + status));
            }
            try { Thread.sleep(properties.pollInterval().toMillis()); }
            catch (InterruptedException e) { Thread.currentThread().interrupt(); throw new DomainException("Interrupted while waiting for Agent Platform execution"); }
        }
        throw new DomainException("Agent Platform execution timed out after " + properties.executionTimeout());
    }

    private static String nullIfBlank(String value) { return value == null || value.isBlank() ? null : value; }
}
