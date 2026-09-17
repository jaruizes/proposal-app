package io.github.jaruizes.proposal.infrastructure.api.rest;

import com.fasterxml.jackson.databind.JsonNode;
import io.github.jaruizes.proposal.infrastructure.client.mcp.McpStdioClient;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/diagnostics/mcp")
public class McpDiagnosticController {

    private final McpStdioClient mcpClient;

    public McpDiagnosticController(McpStdioClient mcpClient) {
        this.mcpClient = mcpClient;
    }

    @GetMapping("/google-workspace")
    public ResponseEntity<Map<String, Object>> googleWorkspace() {
        JsonNode tools = mcpClient.listTools();

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("status", "UP");
        response.put("server", "google-workspace");
        response.put("toolCount", tools.isArray() ? tools.size() : 0);
        response.put("tools", tools);

        return ResponseEntity.ok(response);
    }
}
