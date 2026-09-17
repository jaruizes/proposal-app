import pytest

from agent_platform.application.tools import ToolRegistry, ToolRegistryError
from agent_platform.domain import ToolCall, ToolDefinition, ToolResult


class FakeProvider:
    def __init__(self, key: str, tools: list[ToolDefinition]) -> None:
        self._key = key
        self._tools = tools
        self.calls: list[ToolCall] = []

    @property
    def provider_key(self) -> str:
        return self._key

    async def list_tools(self) -> list[ToolDefinition]:
        return self._tools

    async def invoke(self, call: ToolCall) -> ToolResult:
        self.calls.append(call)
        return ToolResult(
            call_id=call.id,
            tool_key=call.tool_key,
            content=[{"type": "text", "text": "ok"}],
            metadata={"provider": self.provider_key},
        )


@pytest.mark.asyncio
async def test_tool_registry_discovers_and_dispatches_tools() -> None:
    provider = FakeProvider(
        "fake",
        [ToolDefinition(key="drive_search_files", name="Search files", provider="fake")],
    )
    registry = ToolRegistry([provider])

    tools = await registry.list_tools()
    result = await registry.invoke(ToolCall(tool_key="drive_search_files", arguments={"q": "RFP"}))

    assert [tool.key for tool in tools] == ["drive_search_files"]
    assert result.content[0]["text"] == "ok"
    assert provider.calls[0].arguments == {"q": "RFP"}


@pytest.mark.asyncio
async def test_tool_registry_rejects_duplicate_tool_keys() -> None:
    tool = ToolDefinition(key="shared", name="Shared", provider="one")
    one = FakeProvider("one", [tool])
    two = FakeProvider("two", [tool.model_copy(update={"provider": "two"})])
    registry = ToolRegistry([one, two])

    with pytest.raises(ToolRegistryError, match="Duplicate tool key"):
        await registry.refresh()
