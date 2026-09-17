package io.github.jaruizes.proposal.infrastructure.client.mcp;

import com.fasterxml.jackson.databind.JsonNode;
import io.github.jaruizes.proposal.domain.ports.ToolGatewayPort;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import io.micrometer.observation.Observation;
import io.micrometer.observation.ObservationRegistry;
import org.springframework.stereotype.Component;

import java.util.*;

@Component
public class McpToolGatewayAdapter implements ToolGatewayPort {
    private final McpStdioClient client;
    private final ObservationRegistry observationRegistry;
    private final MeterRegistry meterRegistry;

    public McpToolGatewayAdapter(McpStdioClient client, ObservationRegistry observationRegistry, MeterRegistry meterRegistry) {
        this.client = client;
        this.observationRegistry = observationRegistry;
        this.meterRegistry = meterRegistry;
    }

    @Override
    public Map<String,Object> execute(String toolName, Map<String,Object> arguments) {
        var observation = Observation.createNotStarted("proposal.mcp.tool", observationRegistry)
                .lowCardinalityKeyValue("mcp.server", "google-workspace")
                .lowCardinalityKeyValue("mcp.tool", toolName)
                .start();
        var timer = Timer.start(meterRegistry);

        try (var ignored = observation.openScope()) {
            JsonNode result = client.callTool(toolName, arguments);
            var texts = new ArrayList<String>();
            var images = new ArrayList<Map<String,String>>();
            result.path("content").forEach(block -> {
                var type = block.path("type").asText();
                if ("text".equals(type)) texts.add(block.path("text").asText());
                if ("image".equals(type)) images.add(Map.of(
                        "mimeType", block.path("mimeType").asText("image/png"),
                        "data", block.path("data").asText()));
            });

            var isError = result.path("isError").asBoolean(false);
            var status = isError ? "mcp_error" : "success";
            meterRegistry.counter("proposal.mcp.requests", "server", "google-workspace", "tool", toolName, "status", status).increment();
            timer.stop(Timer.builder("proposal.mcp.duration")
                    .description("MCP tool invocation duration")
                    .tag("server", "google-workspace")
                    .tag("tool", toolName)
                    .tag("status", status)
                    .register(meterRegistry));
            observation.lowCardinalityKeyValue("status", status);

            var out = new LinkedHashMap<String,Object>();
            out.put("text", String.join("\n", texts));
            out.put("images", images);
            out.put("isError", isError);
            return out;
        } catch (RuntimeException ex) {
            observation.error(ex);
            meterRegistry.counter("proposal.mcp.requests", "server", "google-workspace", "tool", toolName, "status", "error").increment();
            timer.stop(Timer.builder("proposal.mcp.duration")
                    .description("MCP tool invocation duration")
                    .tag("server", "google-workspace")
                    .tag("tool", toolName)
                    .tag("status", "error")
                    .register(meterRegistry));
            throw ex;
        } finally {
            observation.stop();
        }
    }
}
