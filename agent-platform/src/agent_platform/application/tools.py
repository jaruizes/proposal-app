from __future__ import annotations

import time
from typing import Protocol

from agent_platform.application.observability import TOOL_CALLS, TOOL_LATENCY, timed_span
from agent_platform.domain.tools import ToolCall, ToolDefinition, ToolResult


class ToolProvider(Protocol):
    @property
    def provider_key(self)->str:...
    async def list_tools(self)->list[ToolDefinition]:...
    async def invoke(self,call:ToolCall)->ToolResult:...


class ToolRegistryError(RuntimeError):pass


class ToolRegistry:
    def __init__(self,providers:list[ToolProvider]|None=None)->None:
        self._providers={};self._tools={}
        for provider in providers or []:self.register_provider(provider)
    def register_provider(self,provider):
        key=provider.provider_key
        if key in self._providers:raise ToolRegistryError(f"Duplicate tool provider: {key}")
        self._providers[key]=provider
    async def refresh(self):
        discovered={}
        for provider_key in sorted(self._providers):
            provider=self._providers[provider_key]
            for tool in await provider.list_tools():
                if not tool.enabled:continue
                if tool.key in discovered:raise ToolRegistryError(f"Duplicate tool key '{tool.key}'")
                discovered[tool.key]=(tool,provider)
        self._tools=discovered;return[entry[0] for _,entry in sorted(discovered.items())]
    async def list_tools(self,*,refresh=False):
        if refresh or not self._tools:return await self.refresh()
        return[entry[0] for _,entry in sorted(self._tools.items())]
    async def get(self,tool_key):
        if tool_key not in self._tools:await self.refresh()
        entry=self._tools.get(tool_key);return entry[0] if entry else None
    async def invoke(self,call):
        if call.tool_key not in self._tools:await self.refresh()
        entry=self._tools.get(call.tool_key)
        if entry is None:raise ToolRegistryError(f"Unknown tool: {call.tool_key}")
        tool,provider=entry;started=time.perf_counter()
        with timed_span("tool.invoke",tool=tool.key,provider=provider.provider_key):
            try:
                result=await provider.invoke(call);TOOL_CALLS.labels(tool.key,provider.provider_key,"error" if result.is_error else "ok").inc();return result
            except Exception:
                TOOL_CALLS.labels(tool.key,provider.provider_key,"error").inc();raise
            finally:TOOL_LATENCY.labels(tool.key,provider.provider_key).observe(time.perf_counter()-started)
