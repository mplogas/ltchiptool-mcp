import json

import pytest

from ltchiptool_mcp.server import call_tool


@pytest.mark.asyncio
async def test_legacy_project_path_rejected():
    """Hard rename: passing legacy project_path to a path tool fails loudly."""
    result = await call_tool("prepare_flash_read", {"project_path": "/tmp/x"})
    payload = json.loads(result[0].text)
    assert payload["error"] == "renamed_argument"
    assert "engagement_path" in payload["message"]
