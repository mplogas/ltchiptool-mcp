"""Dispatch tests for ltchiptool-mcp.

Patches every tools.tool_* function with AsyncMock so this tests ONLY
the dispatch routing and argument unpacking, not tool logic.
"""

import json

import pytest
from unittest.mock import patch, AsyncMock
from mcp.types import TextContent

from ltchiptool_mcp import server, tools


TOOL_ARGS: dict[str, dict] = {
    "prepare_chip_info": {"serial_port": "/dev/null", "family": "bk7231n"},
    "start_chip_info": {"serial_port": "/dev/null", "family": "bk7231n"},
    "prepare_flash_read": {"serial_port": "/dev/null", "family": "bk7231n", "engagement_name": "x"},
    "start_flash_read": {"serial_port": "/dev/null", "family": "bk7231n", "engagement_name": "x"},
    "dissect_dump": {"dump_path": "/tmp/x.bin", "family": "bk7231n", "engagement_name": "x"},
    "list_supported_families": {},
    "list_boards": {},
}


@pytest.fixture(autouse=True)
def _mock_tools():
    patches = []
    for name in dir(tools):
        if name.startswith("tool_"):
            patches.append(
                patch.object(
                    tools, name, new_callable=AsyncMock, return_value={"ok": True}
                )
            )
    for p in patches:
        p.start()
    yield
    patch.stopall()


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name,args", TOOL_ARGS.items())
async def test_dispatch(tool_name, args):
    result = await server.call_tool(tool_name, args)
    assert len(result) == 1
    assert isinstance(result[0], TextContent)
    data = json.loads(result[0].text)
    assert "Unknown tool" not in data.get("error", "")


@pytest.mark.asyncio
async def test_unknown_tool_raises():
    with pytest.raises(ValueError, match="Unknown tool"):
        await server.call_tool("nonexistent_tool", {})
