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
                "stderr": "Timeout while linking with the chip",
                "returncode": 1,
                "duration_s": 25.0,
            }
            result = await tool_start_chip_info(serial_port=port, family="bk7231n")

        assert result["error"] == "hitl_window_missed"
        assert "retry" in result["message"].lower()


from ltchiptool_mcp.tools import (
    tool_prepare_flash_read,
    tool_start_flash_read,
)


@pytest.mark.asyncio
class TestPrepareFlashRead:
    async def test_resolves_engagement_path(self, tmp_path):
        port = str(tmp_path / "port")
        (tmp_path / "port").write_bytes(b"")
        proj = tmp_path / "myproject"
        proj.mkdir()
        result = await tool_prepare_flash_read(
            serial_port=port,
            family="bk7231n",
            output_name="dump.bin",
            state_label="paired",
            engagement_path=str(proj),
        )
        assert "operator_instructions" in result
        out_path = result["resolved_paths"]["output"]
        assert out_path.startswith(str(proj))
        assert "uart/raw/dump.bin" in out_path

    async def test_resolves_engagement_name(self, tmp_path, monkeypatch):
        # PIDEV_ENGAGEMENTS_DIR is read by tool to anchor standalone path.
        port = str(tmp_path / "port")
        (tmp_path / "port").write_bytes(b"")
        engagements = tmp_path / "engagements"
        engagements.mkdir()
        monkeypatch.setenv("PIDEV_ENGAGEMENTS_DIR", str(engagements))
        result = await tool_prepare_flash_read(
            serial_port=port,
            family="bk7231n",
            output_name="dump.bin",
            engagement_name="testdev",
        )
        out_path = result["resolved_paths"]["output"]
        assert "testdev/uart/raw/dump.bin" in out_path


@pytest.mark.asyncio
class TestStartFlashRead:
    async def test_invokes_ltchiptool_flash_read(self, tmp_path):
        port = str(tmp_path / "port")
        (tmp_path / "port").write_bytes(b"")
        proj = tmp_path / "proj"
        proj.mkdir()

        with patch("ltchiptool_mcp.tools.run_ltchiptool") as mock_run:
            mock_run.return_value = {
                "stdout": "Reading Flash (2 MiB)... done",
                "stderr": "",
                "returncode": 0,
                "duration_s": 200.0,
            }
            result = await tool_start_flash_read(
                serial_port=port,
                family="bk7231n",
                output_name="dump.bin",
                engagement_path=str(proj),
            )

        argv = mock_run.call_args[0][0]
        assert argv[0:3] == ["flash", "read", "bk7231n"]
        assert argv[3] == "-d"
        assert argv[4] == port
        assert "uart/raw/dump.bin" in argv[5]
        assert result["dump_path"].endswith("uart/raw/dump.bin")
        # Subprocess was mocked so the .bin file was never written.
        # size_bytes will be 0 and size_ok False; that's expected here.
        assert result["size_bytes"] == 0
        assert result["size_ok"] is False

    @pytest.mark.asyncio
    async def test_hitl_window_missed_returns_structured_error(self, tmp_path):
        port = str(tmp_path / "fake_port")
        (tmp_path / "fake_port").write_bytes(b"")
        proj = tmp_path / "proj"
        proj.mkdir()

        with patch("ltchiptool_mcp.tools.run_ltchiptool") as mock_run:
            mock_run.return_value = {
                "stdout": "",
                "stderr": "Timeout while linking with the chip",
                "returncode": 1,
                "duration_s": 25.0,
            }
            result = await tool_start_flash_read(
                serial_port=port,
                family="bk7231n",
                output_name="dump.bin",
                engagement_path=str(proj),
            )

        assert result["error"] == "hitl_window_missed"
        assert "retry" in result["message"].lower()


from ltchiptool_mcp.tools import tool_dissect_dump


@pytest.mark.asyncio
class TestDissectDump:
    async def test_invokes_runner_and_parses(self, tmp_path):
        dump = tmp_path / "dump.bin"
        dump.write_bytes(b"\x00" * 1024)
        proj = tmp_path / "proj"
        proj.mkdir()

        fake_dissect_stdout = (
            "RBL containers:\n"
            "    0x10f9a: bootloader - [encoding_algorithm=NONE, size=0xea20]\n"
            "        extracted to /tmp/x/\n"
            "Storage partition:\n"
            "    0x1ee000: 32 KiB - 1 keys\n"
            "    - 'gw_bi'\n"
            "        extracted all keys to /tmp/x/dump_storage.json\n"
        )

        with patch("ltchiptool_mcp.tools.run_dissect") as mock_run:
            mock_run.return_value = {
                "stdout": fake_dissect_stdout,
                "stderr": "",
                "returncode": 0,
                "duration_s": 0.5,
            }
            result = await tool_dissect_dump(
                dump_path=str(dump),
                family="bk7231n",
                state_label="paired",
                engagement_path=str(proj),
            )

        assert result["family"] == "bk7231n"
        assert result["state_label"] == "paired"
        assert result["output_dir"].endswith("uart/decrypted/paired")
        assert len(result["rbl_containers"]) == 1
        assert "gw_bi" in result["storage_partition"]["keys"]

    async def test_missing_dump_returns_error(self, tmp_path):
        result = await tool_dissect_dump(
            dump_path=str(tmp_path / "does_not_exist.bin"),
            family="bk7231n",
            engagement_name="x",
        )
        assert result["error"] == "input_not_found"

    async def test_unknown_family_returns_error(self, tmp_path):
        dump = tmp_path / "dump.bin"
        dump.write_bytes(b"\x00")
        result = await tool_dissect_dump(
            dump_path=str(dump),
            family="ln882h",
            engagement_name="x",
        )
        assert result["error"] == "unsupported_family"

    async def test_pycryptodome_missing_warning_returns_error(self, tmp_path):
        """When bk7231tools prints 'skipping storage decryption' due to missing
        pycryptodome, surface as a hard error rather than passing a partial
        result. Returncode is 0 in this scenario but the result is incomplete.
        """
        dump = tmp_path / "dump.bin"
        dump.write_bytes(b"\x00" * 1024)
        proj = tmp_path / "proj"
        proj.mkdir()

        partial_stdout = (
            "RBL containers:\n"
            "    0x10f9a: bootloader - [encoding_algorithm=NONE, size=0xea20]\n"
            "        extracted to /tmp/x/\n"
            "    0x129f0a: app - [encoding_algorithm=NONE, size=0xe60a0]\n"
            "        extracted to /tmp/x/\n"
            "NOTE: skipping storage decryption because of missing PyCryptodome dependency.\n"
            "      Install using 'pip install bk7231tools[cli]' to add the dependency.\n"
        )

        with patch("ltchiptool_mcp.tools.run_dissect") as mock_run:
            mock_run.return_value = {
                "stdout": partial_stdout,
                "stderr": "",
                "returncode": 0,
                "duration_s": 0.5,
            }
            result = await tool_dissect_dump(
                dump_path=str(dump),
                family="bk7231n",
                state_label="paired",
                engagement_path=str(proj),
            )

        assert result["error"] == "missing_storage_crypto_dep"
        assert "pycryptodome" in result["message"].lower()
