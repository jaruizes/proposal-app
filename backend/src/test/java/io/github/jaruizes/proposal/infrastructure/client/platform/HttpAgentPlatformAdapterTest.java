package io.github.jaruizes.proposal.infrastructure.client.platform;

import com.sun.net.httpserver.HttpServer;
import io.github.jaruizes.proposal.domain.model.AgentTask;
import io.github.jaruizes.proposal.domain.model.PhaseType;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.web.reactive.function.client.WebClient;

import java.net.InetSocketAddress;
import java.time.Duration;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;

class HttpAgentPlatformAdapterTest {
    private HttpServer server;

    @AfterEach
    void stop() {
        if (server != null) server.stop(0);
    }

    @Test
    void submitsPollsAndReturnsPlatformArtifact() throws Exception {
        var polls = new AtomicInteger();
        var submittedBody = new java.util.concurrent.atomic.AtomicReference<String>();
        server = HttpServer.create(new InetSocketAddress(0), 0);
        server.createContext("/v1/executions", exchange -> {
            if ("POST".equals(exchange.getRequestMethod())) {
                submittedBody.set(new String(exchange.getRequestBody().readAllBytes(), java.nio.charset.StandardCharsets.UTF_8));
                respond(exchange, 202, "{\"id\":\"11111111-1111-1111-1111-111111111111\",\"status\":\"QUEUED\",\"agent_key\":\"business-analyst\",\"objective\":\"x\"}");
            }
            else respond(exchange, 404, "{}");
        });
        server.createContext("/v1/executions/11111111-1111-1111-1111-111111111111", exchange -> {
            polls.incrementAndGet();
            respond(exchange, 200, "{\"id\":\"11111111-1111-1111-1111-111111111111\",\"status\":\"COMPLETED\",\"agent_key\":\"business-analyst\",\"objective\":\"x\",\"usage\":{}}");
        });
        server.createContext("/v1/executions/11111111-1111-1111-1111-111111111111/result", exchange -> respond(exchange, 200,
                "{\"execution_id\":\"11111111-1111-1111-1111-111111111111\",\"status\":\"COMPLETED\",\"artifacts\":[{\"type\":\"AGENT_OUTPUT\",\"content\":\"# Analysis\\nOK\"}],\"usage\":{\"input_tokens\":12,\"output_tokens\":4},\"model\":\"claude-test\",\"provider_request_id\":\"msg_1\"}"));
        server.start();

        var props = new AgentPlatformProperties("http://localhost:" + server.getAddress().getPort(), "", Duration.ofMillis(1), Duration.ofSeconds(2));
        var adapter = new HttpAgentPlatformAdapter(props, WebClient.builder());
        var task = AgentTask.of(UUID.randomUUID(), PhaseType.ANALYSIS, "business-analyst", "analyze-opportunity", "Analyze", "Return analysis");

        var result = adapter.execute(task, "claude-test", "Customer context", List.of());

        assertThat(result.content()).contains("# Analysis");
        assertThat(submittedBody.get()).contains("\"output_format\":\"markdown\"");
        assertThat(result.model()).isEqualTo("claude-test");
        assertThat(result.inputTokens()).isEqualTo(12);
        assertThat(result.outputTokens()).isEqualTo(4);
        assertThat(result.requestId()).isEqualTo("msg_1");
        assertThat(polls.get()).isGreaterThanOrEqualTo(1);
    }

    private static void respond(com.sun.net.httpserver.HttpExchange exchange, int status, String body) throws java.io.IOException {
        var bytes = body.getBytes(java.nio.charset.StandardCharsets.UTF_8);
        exchange.getResponseHeaders().add("Content-Type", "application/json");
        exchange.sendResponseHeaders(status, bytes.length);
        try (var output = exchange.getResponseBody()) { output.write(bytes); }
    }
}
