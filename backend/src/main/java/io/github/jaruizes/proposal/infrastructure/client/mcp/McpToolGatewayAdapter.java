package io.github.jaruizes.proposal.infrastructure.client.mcp;

import com.fasterxml.jackson.databind.JsonNode;
import io.github.jaruizes.proposal.domain.ports.ToolGatewayPort;
import org.springframework.stereotype.Component;

import java.util.*;

@Component
public class McpToolGatewayAdapter implements ToolGatewayPort {
    private final McpStdioClient client;
    public McpToolGatewayAdapter(McpStdioClient client) { this.client = client; }

    @Override
    public Map<String,Object> execute(String toolName, Map<String,Object> arguments) {
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
        var out = new LinkedHashMap<String,Object>();
        out.put("text", String.join("\n", texts));
        out.put("images", images);
        out.put("isError", result.path("isError").asBoolean(false));
        return out;
    }
}
