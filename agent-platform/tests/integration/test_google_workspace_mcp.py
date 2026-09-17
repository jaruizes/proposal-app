import os

import pytest

from agent_platform.config import Settings
from agent_platform.providers.mcp import McpServerDefinition, McpToolProvider


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_google_workspace_mcp_exposes_expected_tools() -> None:
    if os.getenv("RUN_GOOGLE_WORKSPACE_MCP_INTEGRATION") != "1":
        pytest.skip("Set RUN_GOOGLE_WORKSPACE_MCP_INTEGRATION=1 to run the real MCP smoke test")

    settings = Settings()
    provider = McpToolProvider(
        McpServerDefinition(
            key="google-workspace",
            command=settings.google_workspace_mcp_command,
            args=(settings.google_workspace_mcp_script,),
            cwd=settings.google_workspace_mcp_cwd,
            timeout_seconds=settings.google_workspace_mcp_timeout_seconds,
        )
    )

    tools = {tool.key for tool in await provider.list_tools()}
    assert {
        "drive_search_files",
        "drive_list_folder",
        "slides_get_presentation",
        "docs_get_document",
        "sheets_get_values",
    }.issubset(tools)
