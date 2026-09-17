from __future__ import annotations

from typing import Protocol

from agent_platform.domain.tools import ToolCall, ToolDefinition, ToolResult


class ToolProvider(Protocol):
    """Provider-neutral port implemented by MCP and future native providers."""

    @property
    def provider_key(self) -> str: ...

    async def list_tools(self) -> list[ToolDefinition]: ...

    async def invoke(self, call: ToolCall) -> ToolResult: ...


class ToolRegistryError(RuntimeError):
    pass


class ToolRegistry:
    """Aggregates tool providers and provides deterministic discovery/dispatch."""

    def __init__(self, providers: list[ToolProvider] | None = None) -> None:
        self._providers: dict[str, ToolProvider] = {}
        self._tools: dict[str, tuple[ToolDefinition, ToolProvider]] = {}
        for provider in providers or []:
            self.register_provider(provider)

    def register_provider(self, provider: ToolProvider) -> None:
        key = provider.provider_key
        if key in self._providers:
            raise ToolRegistryError(f"Duplicate tool provider: {key}")
        self._providers[key] = provider

    async def refresh(self) -> list[ToolDefinition]:
        discovered: dict[str, tuple[ToolDefinition, ToolProvider]] = {}
        for provider_key in sorted(self._providers):
            provider = self._providers[provider_key]
            for tool in await provider.list_tools():
                if not tool.enabled:
                    continue
                if tool.key in discovered:
                    other = discovered[tool.key][0]
                    raise ToolRegistryError(
                        f"Duplicate tool key '{tool.key}' from providers "
                        f"'{other.provider}' and '{tool.provider}'"
                    )
                discovered[tool.key] = (tool, provider)
        self._tools = discovered
        return [entry[0] for _, entry in sorted(discovered.items())]

    async def list_tools(self, *, refresh: bool = False) -> list[ToolDefinition]:
        if refresh or not self._tools:
            return await self.refresh()
        return [entry[0] for _, entry in sorted(self._tools.items())]

    async def get(self, tool_key: str) -> ToolDefinition | None:
        if tool_key not in self._tools:
            await self.refresh()
        entry = self._tools.get(tool_key)
        return entry[0] if entry else None

    async def invoke(self, call: ToolCall) -> ToolResult:
        if call.tool_key not in self._tools:
            await self.refresh()
        entry = self._tools.get(call.tool_key)
        if entry is None:
            raise ToolRegistryError(f"Unknown tool: {call.tool_key}")
        _, provider = entry
        return await provider.invoke(call)
