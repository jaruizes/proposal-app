package io.github.jaruizes.proposal.infrastructure.client.mcp;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PreDestroy;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;

/** Minimal MCP client for the same Google Workspace stdio server used by proposal-copilot. */
@Component
public class McpStdioClient {
    private final ObjectMapper json = new ObjectMapper();
    private final AtomicLong ids = new AtomicLong(1);
    private final String command;
    private final String script;
    private Process process;
    private BufferedWriter writer;
    private BufferedReader reader;

    public McpStdioClient(@Value("${mcp.google-workspace.command:node}") String command,
                          @Value("${mcp.google-workspace.script:/app/mcp/google-workspace/dist/server.js}") String script) {
        this.command = command;
        this.script = script;
    }

    public synchronized JsonNode callTool(String name, Map<String,Object> arguments) {
        ensureStarted();
        return request("tools/call", Map.of("name", name, "arguments", arguments)).path("result");
    }

    private void ensureStarted() {
        if (process != null && process.isAlive()) return;
        try {
            var pb = new ProcessBuilder(command, script);
            pb.redirectError(ProcessBuilder.Redirect.INHERIT);
            process = pb.start();
            writer = new BufferedWriter(new OutputStreamWriter(process.getOutputStream(), StandardCharsets.UTF_8));
            reader = new BufferedReader(new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8));
            request("initialize", Map.of(
                    "protocolVersion", "2025-06-18",
                    "capabilities", Map.of(),
                    "clientInfo", Map.of("name", "proposal-agent-platform", "version", "0.2.0")));
            notify("notifications/initialized", Map.of());
        } catch (IOException e) {
            throw new IllegalStateException("Cannot start Google Workspace MCP server. Verify Google OAuth token and MCP build.", e);
        }
    }

    private JsonNode request(String method, Object params) {
        var id = ids.getAndIncrement();
        try {
            var payload = json.createObjectNode();
            payload.put("jsonrpc", "2.0");
            payload.put("id", id);
            payload.put("method", method);
            payload.set("params", json.valueToTree(params));
            writer.write(json.writeValueAsString(payload));
            writer.newLine();
            writer.flush();
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.isBlank()) continue;
                var response = json.readTree(line);
                if (response.has("id") && response.path("id").asLong(-1) == id) {
                    if (response.has("error")) throw new IllegalStateException("MCP error: " + response.get("error"));
                    return response;
                }
            }
            throw new IllegalStateException("Google Workspace MCP process ended unexpectedly");
        } catch (IOException e) {
            stop();
            throw new IllegalStateException("MCP stdio communication failed", e);
        }
    }

    private void notify(String method, Object params) throws IOException {
        var payload = json.createObjectNode();
        payload.put("jsonrpc", "2.0");
        payload.put("method", method);
        payload.set("params", json.valueToTree(params));
        writer.write(json.writeValueAsString(payload));
        writer.newLine();
        writer.flush();
    }

    @PreDestroy
    public synchronized void stop() {
        if (process != null) process.destroy();
        process = null;
        writer = null;
        reader = null;
    }
}
