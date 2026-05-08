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


from ltchiptool_mcp.tools import (
    tool_prepare_chip_info,
    tool_start_chip_info,
)


@pytest.mark.asyncio
class TestPrepareChipInfo:
    async def test_returns_operator_instructions(self, tmp_path):
        # Need a fake serial port: tmp_path is a real existing path which
        # passes our 'exists' check.
        port = str(tmp_path / "fake_port")
        # Touch the file so Path(port).exists() is True
        (tmp_path / "fake_port").write_bytes(b"")
        result = await tool_prepare_chip_info(serial_port=port, family="bk7231n")
        assert "operator_instructions" in result
        assert "yank" in result["operator_instructions"].lower()
        assert result["window_seconds"] == 20
        assert result["ready_to_start"] is True

    async def test_unknown_family_returns_error(self, tmp_path):
        port = str(tmp_path / "fake_port")
        (tmp_path / "fake_port").write_bytes(b"")
        result = await tool_prepare_chip_info(serial_port=port, family="ln882h")
        assert "error" in result
        assert "supported" in result.get("message", "").lower()

    async def test_missing_port_returns_error(self):
        result = await tool_prepare_chip_info(
            serial_port="/dev/does_not_exist_xyz",
            family="bk7231n",
        )
        assert "error" in result
        assert "port" in result.get("message", "").lower()


@pytest.mark.asyncio
class TestStartChipInfo:
    async def test_invokes_runner_with_correct_args(self, tmp_path):
        port = str(tmp_path / "fake_port")
        (tmp_path / "fake_port").write_bytes(b"")

        # Real-looking parsed output (we use an empty fixture stub that the
        # parser handles via the normal table extraction).
        with patch("ltchiptool_mcp.tools.run_ltchiptool") as mock_run:
            mock_run.return_value = {
                "stdout": "(chip info table)",
                "stderr": "",
                "returncode": 0,
                "duration_s": 1.2,
            }
            with patch(
                "ltchiptool_mcp.tools.get_strategy"
            ) as mock_get:
                strat = MagicMock()
                strat.ltchiptool_arg = "bk7231n"
                strat.hitl_window_seconds = 20
                strat.chip_info_parser = lambda s: {"chip_type": "BK7231N"}
                mock_get.return_value = strat

                result = await tool_start_chip_info(serial_port=port, family="bk7231n")

        argv = mock_run.call_args[0][0]
        assert argv == ["flash", "info", "bk7231n", "-d", port]
        assert result["chip_info"]["chip_type"] == "BK7231N"
        assert result["duration_s"] == 1.2

    async def test_hitl_window_missed_returns_structured_error(self, tmp_path):
        port = str(tmp_path / "fake_port")
        (tmp_path / "fake_port").write_bytes(b"")
        with patch("ltchiptool_mcp.tools.run_ltchiptool") as mock_run:
            mock_run.return_value = {
                "stdout": "",
                "stderr": "Connecting to ... timeout",
                "returncode": 1,
                "duration_s": 25.0,
            }
            result = await tool_start_chip_info(serial_port=port, family="bk7231n")

        assert result["error"] == "hitl_window_missed"
        assert "retry" in result["message"].lower()
