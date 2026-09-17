from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from agent_platform.api.dependencies import McpRegistryDep, ToolRegistryDep
from agent_platform.application.tools import ToolRegistryError
from agent_platform.domain import ToolCall, ToolDefinition, ToolResult


router = APIRouter(prefix="/v1", tags=["tools"])


class ToolInvokeRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)
    correlation_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class McpServerResponse(BaseModel):
    key: str
    command: str
    args: list[str]
    enabled: bool


@router.get("/tools", response_model=list[ToolDefinition])
async def list_tools(
    registry: ToolRegistryDep,
    refresh: bool = Query(default=False),
) -> list[ToolDefinition]:
    try:
        return await registry.list_tools(refresh=refresh)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Tool discovery failed: {exc}") from exc


@router.post("/tools/{tool_key}/invoke", response_model=ToolResult)
async def invoke_tool(
    tool_key: str,
    request: ToolInvokeRequest,
    registry: ToolRegistryDep,
) -> ToolResult:
    try:
        return await registry.invoke(
            ToolCall(
                tool_key=tool_key,
                arguments=request.arguments,
                correlation_id=request.correlation_id,
                metadata=request.metadata,
            )
        )
    except ToolRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/mcp/servers", response_model=list[McpServerResponse], tags=["mcp"])
def list_mcp_servers(registry: McpRegistryDep) -> list[McpServerResponse]:
    return [
        McpServerResponse(
            key=server.key,
            command=server.command,
            args=list(server.args),
            enabled=server.enabled,
        )
        for server in registry.list_servers()
    ]
