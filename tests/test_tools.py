# tests/test_tools.py
from unittest.mock import patch, MagicMock

import pytest

from ltchiptool_mcp.tools import (
    tool_list_supported_families,
    tool_list_boards,
)


@pytest.mark.asyncio
class TestListSupportedFamilies:
    async def test_returns_registered_families(self):
        result = await tool_list_supported_families()
        names = {f["name"] for f in result["families"]}
        assert "bk7231n" in names
        assert "bk7231t" in names

    async def test_each_family_has_action_and_window(self):
        result = await tool_list_supported_families()
        for f in result["families"]:
            assert "hitl_action" in f
            assert "hitl_window_seconds" in f
            assert isinstance(f["hitl_window_seconds"], int)


@pytest.mark.asyncio
class TestListBoards:
    async def test_invokes_runner_and_parses(self):
        fake_stdout = "..."  # fixture content not important here
        with patch(
            "ltchiptool_mcp.tools.run_list_boards",
            return_value={"stdout": fake_stdout, "stderr": "", "returncode": 0, "duration_s": 0.1},
        ), patch(
            "ltchiptool_mcp.tools.parse_list_boards",
            return_value=[{"name": "CB3S", "family": "bk7231n"}],
        ):
            result = await tool_list_boards()

        assert result["count"] == 1
        assert result["boards"][0]["name"] == "CB3S"

    async def test_returns_error_on_runner_failure(self):
        with patch(
            "ltchiptool_mcp.tools.run_list_boards",
            return_value={"stdout": "", "stderr": "boom", "returncode": 1, "duration_s": 0.0},
        ):
            result = await tool_list_boards()

        assert "error" in result
