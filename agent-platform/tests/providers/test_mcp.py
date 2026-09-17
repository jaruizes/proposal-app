import sys

import pytest

from agent_platform.domain import ToolCall
from agent_platform.providers.mcp import McpServerDefinition, McpToolProvider


FAKE_MCP = r'''
import json, sys
for line in sys.stdin:
    msg=json.loads(line)
    method=msg.get("method")
    if "id" not in msg:
        continue
    if method=="initialize":
        result={"protocolVersion":"2025-06-18","capabilities":{"tools":{}},"serverInfo":{"name":"fake","version":"1"}}
    elif method=="tools/list":
        result={"tools":[{"name":"echo","description":"Echo input","inputSchema":{"type":"object"}}]}
    elif method=="tools/call":
        result={"content":[{"type":"text","text":msg["params"]["arguments"].get("value","")}],"isError":False}
    else:
        print(json.dumps({"jsonrpc":"2.0","id":msg["id"],"error":{"code":-32601,"message":"not found"}}), flush=True)
        continue
    print(json.dumps({"jsonrpc":"2.0","id":msg["id"],"result":result}), flush=True)
'''


@pytest.mark.asyncio
async def test_mcp_stdio_provider_discovers_and_invokes_tools() -> None:
    provider = McpToolProvider(
        McpServerDefinition(
            key="fake",
            command=sys.executable,
            args=("-u", "-c", FAKE_MCP),
            timeout_seconds=2,
        )
    )

    tools = await provider.list_tools()
    result = await provider.invoke(ToolCall(tool_key="echo", arguments={"value": "hello"}))

    assert [tool.key for tool in tools] == ["echo"]
    assert tools[0].provider == "mcp:fake"
    assert tools[0].server == "fake"
    assert result.is_error is False
    assert result.content == [{"type": "text", "text": "hello"}]
