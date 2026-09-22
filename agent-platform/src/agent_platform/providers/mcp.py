from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import Any

from agent_platform.application.tools import ToolProvider
from agent_platform.domain import ToolCall, ToolDefinition, ToolError, ToolResult


MCP_PROTOCOL_VERSION = "2025-06-18"


class McpProtocolError(RuntimeError):
    pass


@dataclass(frozen=True)
class McpServerDefinition:
    key: str
    command: str
    args: tuple[str, ...] = ()
    cwd: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    timeout_seconds: float = 30.0
    max_message_bytes: int = 16 * 1024 * 1024
    enabled: bool = True


class McpStdioSession:
    """Minimal MCP JSON-RPC stdio session, independent from any MCP framework."""

    def __init__(self, server: McpServerDefinition) -> None:
        self._server = server
        self._process: asyncio.subprocess.Process | None = None
        self._next_id = 1

    async def __aenter__(self) -> "McpStdioSession":
        env = os.environ.copy()
        env.update(self._server.env)
        self._process = await asyncio.create_subprocess_exec(
            self._server.command,
            *self._server.args,
            cwd=self._server.cwd,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            limit=self._server.max_message_bytes,
        )
        try:
            result = await self.request(
                "initialize",
                {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "proposal-agent-platform", "version": "0.1.0"},
                },
            )
            if not result.get("serverInfo"):
                raise McpProtocolError(f"MCP server '{self._server.key}' returned no serverInfo")
            await self.notify("notifications/initialized", {})
            return self
        except Exception:
            await self.close()
            raise

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def close(self) -> None:
        if self._process is None:
            return
        if self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()
        self._process = None

    async def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        await self._write({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        while True:
            message = await self._read()
            if message.get("id") != request_id:
                continue
            if "error" in message:
                error = message["error"]
                raise McpProtocolError(
                    f"MCP {method} failed ({error.get('code')}): {error.get('message', 'unknown error')}"
                )
            result = message.get("result", {})
            if not isinstance(result, dict):
                raise McpProtocolError(f"MCP {method} returned a non-object result")
            return result

    async def notify(self, method: str, params: dict[str, Any]) -> None:
        await self._write({"jsonrpc": "2.0", "method": method, "params": params})

    async def _write(self, payload: dict[str, Any]) -> None:
        if self._process is None or self._process.stdin is None:
            raise McpProtocolError("MCP process is not running")
        self._process.stdin.write((json.dumps(payload, separators=(",", ":")) + "\n").encode())
        await self._process.stdin.drain()

    async def _read(self) -> dict[str, Any]:
        if self._process is None or self._process.stdout is None:
            raise McpProtocolError("MCP process is not running")
        try:
            raw = await asyncio.wait_for(
                self._process.stdout.readline(), timeout=self._server.timeout_seconds
            )
        except asyncio.TimeoutError as exc:
            raise McpProtocolError(f"MCP server '{self._server.key}' timed out") from exc
        except (ValueError, asyncio.LimitOverrunError) as exc:
            raise McpProtocolError(
                f"MCP server '{self._server.key}' returned a message larger than "
                f"{self._server.max_message_bytes} bytes. Increase the platform MCP message limit "
                "or make the tool return a bounded/reference-based result."
            ) from exc
        if not raw:
            code = await self._process.wait()
            raise McpProtocolError(f"MCP server '{self._server.key}' exited with code {code}")
        try:
            message = json.loads(raw.decode())
        except json.JSONDecodeError as exc:
            raise McpProtocolError(f"Invalid JSON from MCP server '{self._server.key}'") from exc
        if not isinstance(message, dict):
            raise McpProtocolError("Invalid MCP message")
        return message


class McpToolProvider(ToolProvider):
    def __init__(self, server: McpServerDefinition) -> None:
        self.server = server

    @property
    def provider_key(self) -> str:
        return f"mcp:{self.server.key}"

    async def list_tools(self) -> list[ToolDefinition]:
        async with McpStdioSession(self.server) as session:
            result = await session.request("tools/list", {})
        tools: list[ToolDefinition] = []
        for raw in result.get("tools", []):
            name = raw.get("name")
            if not name:
                continue
            tools.append(
                ToolDefinition(
                    key=name,
                    name=raw.get("title") or name,
                    description=raw.get("description", ""),
                    input_schema=raw.get("inputSchema") or {},
                    provider=self.provider_key,
                    server=self.server.key,
                    metadata={"mcp": True},
                )
            )
        return tools

    async def invoke(self, call: ToolCall) -> ToolResult:
        try:
            async with McpStdioSession(self.server) as session:
                raw = await session.request(
                    "tools/call", {"name": call.tool_key, "arguments": call.arguments}
                )
        except McpProtocolError as exc:
            return ToolResult(
                call_id=call.id,
                tool_key=call.tool_key,
                is_error=True,
                error=ToolError(code="MCP_PROTOCOL_ERROR", message=str(exc), retryable=True),
                metadata={"provider": self.provider_key, "server": self.server.key},
            )

        is_error = bool(raw.get("isError", False))
        return ToolResult(
            call_id=call.id,
            tool_key=call.tool_key,
            content=raw.get("content") or [],
            structured_content=raw.get("structuredContent"),
            is_error=is_error,
            error=(
                ToolError(code="MCP_TOOL_ERROR", message=_content_text(raw.get("content") or []))
                if is_error
                else None
            ),
            metadata={"provider": self.provider_key, "server": self.server.key},
        )


def _content_text(content: list[dict[str, Any]]) -> str:
    parts = [str(item.get("text", "")) for item in content if item.get("type") == "text"]
    return "\n".join(part for part in parts if part) or "MCP tool returned an error"


class McpRegistry:
    """Registry of MCP servers. Tool discovery remains delegated to ToolRegistry."""

    def __init__(self) -> None:
        self._servers: dict[str, McpServerDefinition] = {}

    def register(self, server: McpServerDefinition) -> None:
        if server.key in self._servers:
            raise ValueError(f"Duplicate MCP server: {server.key}")
        self._servers[server.key] = server

    def list_servers(self) -> list[McpServerDefinition]:
        return [self._servers[key] for key in sorted(self._servers)]

    def get(self, key: str) -> McpServerDefinition | None:
        return self._servers.get(key)

    def tool_providers(self) -> list[McpToolProvider]:
        return [McpToolProvider(server) for server in self.list_servers() if server.enabled]
