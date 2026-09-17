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

/**
 * Minimal synchronous MCP stdio client used by the backend to talk to the
 * Google Workspace MCP server bundled with Proposal Copilot.
 */
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

    public synchronized JsonNode callTool(String name, Map<String, Object> arguments) {
        ensureStarted();
        JsonNode result = request("tools/call", Map.of("name", name, "arguments", arguments)).path("result");
        if (result.isMissingNode() || result.isNull()) {
            throw new IllegalStateException("MCP tool returned no result: " + name);
        }
        return result;
    }

    public synchronized JsonNode listTools() {
        ensureStarted();
        return request("tools/list", Map.of()).path("result").path("tools");
    }

    private void ensureStarted() {
        if (process != null && process.isAlive()) {
            return;
        }

        stop();
        try {
            var pb = new ProcessBuilder(command, script);
            pb.redirectError(ProcessBuilder.Redirect.INHERIT);
            process = pb.start();
            writer = new BufferedWriter(new OutputStreamWriter(process.getOutputStream(), StandardCharsets.UTF_8));
            reader = new BufferedReader(new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8));

            JsonNode initialize = request("initialize", Map.of(
                    "protocolVersion", "2025-06-18",
                    "capabilities", Map.of(),
                    "clientInfo", Map.of("name", "proposal-agent-platform", "version", "0.2.0")));

            if (!initialize.path("result").has("serverInfo")) {
                throw new IllegalStateException("Google Workspace MCP returned an invalid initialize response");
            }

            notify("notifications/initialized", Map.of());

            JsonNode tools = request("tools/list", Map.of()).path("result").path("tools");
            if (!tools.isArray() || tools.isEmpty()) {
                throw new IllegalStateException("Google Workspace MCP initialized but exposed no tools");
            }
        } catch (IOException | RuntimeException e) {
            stop();
            throw new IllegalStateException(
                    "Cannot start Google Workspace MCP server. Verify MCP build, Node.js and Google OAuth token.", e);
        }
    }

    private JsonNode request(String method, Object params) {
        long id = ids.getAndIncrement();
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
                if (line.isBlank()) {
                    continue;
                }

                JsonNode response = json.readTree(line);
                if (!response.has("id") || response.path("id").asLong(-1) != id) {
                    // Notifications and responses for other ids are ignored by this
                    // synchronous client. Calls are serialized by synchronized methods.
                    continue;
                }

                if (response.has("error")) {
                    throw new IllegalStateException("MCP " + method + " failed: " + response.get("error"));
                }
                return response;
            }

            throw new IllegalStateException("Google Workspace MCP process ended while waiting for " + method);
        } catch (IOException e) {
            stop();
            throw new IllegalStateException("MCP stdio communication failed during " + method, e);
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
        if (process != null) {
            process.destroy();
        }
        process = null;
        writer = null;
        reader = null;
    }
}
