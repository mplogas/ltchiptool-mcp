from pathlib import Path

import pytest

from ltchiptool_mcp.parsers import parse_bk7231_chip_info

FIXTURES = Path(__file__).parent / "fixtures"


class TestParseBK7231ChipInfo:
    @pytest.fixture
    def real_output(self):
        return (FIXTURES / "flash_info_bk7231n.txt").read_text()

    def test_extracts_chip_type(self, real_output):
        result = parse_bk7231_chip_info(real_output)
        assert result["chip_type"] == "BK7231N"

    def test_extracts_bootloader(self, real_output):
        result = parse_bk7231_chip_info(real_output)
        assert result["bootloader"] == "BK7231N 1.0.1"

    def test_extracts_chip_id(self, real_output):
        result = parse_bk7231_chip_info(real_output)
        assert result["chip_id"] == "0x7231c"

    def test_extracts_mac_address(self, real_output):
        result = parse_bk7231_chip_info(real_output)
        assert result["mac_address"] == "00:11:22:33:44:55"

    def test_extracts_flash_id(self, real_output):
        result = parse_bk7231_chip_info(real_output)
        assert result["flash_id"] == "EB 60 15"

    def test_extracts_flash_size_bytes(self, real_output):
        result = parse_bk7231_chip_info(real_output)
        assert result["flash_size_bytes"] == 2 * 1024 * 1024

    def test_extracts_encryption_key(self, real_output):
        result = parse_bk7231_chip_info(real_output)
        assert result["encryption_key"] == "deadbeef cafebabe 12345678 abcdef00"

    def test_empty_input_raises(self):
        with pytest.raises(ValueError, match="No chip info table"):
            parse_bk7231_chip_info("")

    def test_malformed_input_raises(self):
        with pytest.raises(ValueError, match="No chip info table"):
            parse_bk7231_chip_info("just some random text\nwith no table here")


from ltchiptool_mcp.parsers import parse_bk7231_dissect_dump


class TestParseBK7231DissectDump:
    @pytest.fixture
    def real_output(self):
        return (FIXTURES / "dissect_dump_paired.txt").read_text()

    def test_extracts_rbl_container_count(self, real_output):
        result = parse_bk7231_dissect_dump(real_output)
        assert len(result["rbl_containers"]) == 2

    def test_extracts_bootloader_container(self, real_output):
        result = parse_bk7231_dissect_dump(real_output)
        bl = next(c for c in result["rbl_containers"] if c["name"] == "bootloader")
        assert bl["offset"] == 0x10f9a
        assert bl["size"] == 0xea20
        assert bl["encoding"] == "NONE"

    def test_extracts_app_container(self, real_output):
        result = parse_bk7231_dissect_dump(real_output)
        app = next(c for c in result["rbl_containers"] if c["name"] == "app")
        assert app["offset"] == 0x129f0a
        assert app["size"] == 0xe60a0

    def test_extracts_storage_partition(self, real_output):
        result = parse_bk7231_dissect_dump(real_output)
        sp = result["storage_partition"]
        assert sp["offset"] == 0x1ee000
        assert sp["size_kib"] == 32
        assert sp["key_count"] == 17

    def test_extracts_storage_keys(self, real_output):
        result = parse_bk7231_dissect_dump(real_output)
        keys = result["storage_partition"]["keys"]
        assert "gw_bi" in keys
        assert "gw_wsm" in keys
        assert "ble_beaconkey" in keys
        assert len(keys) == 17

    def test_extracts_storage_json_path(self, real_output):
        result = parse_bk7231_dissect_dump(real_output)
        assert result["storage_partition"]["json_path"].endswith("_storage.json")

    def test_user_param_key_not_found_recorded(self, real_output):
        result = parse_bk7231_dissect_dump(real_output)
        assert result["user_param_key_present"] is False

    def test_empty_input_returns_empty_structure(self):
        result = parse_bk7231_dissect_dump("")
        assert result["rbl_containers"] == []
        assert result["storage_partition"] is None
        assert result["user_param_key_present"] is False


from ltchiptool_mcp.parsers import parse_list_boards


class TestParseListBoards:
    @pytest.fixture
    def real_output(self):
        return (FIXTURES / "list_boards.txt").read_text()

    def test_returns_non_empty_list_of_dicts(self, real_output):
        result = parse_list_boards(real_output)
        assert isinstance(result, list)
        assert len(result) > 30  # ltchiptool ships ~50+ boards
        assert all(isinstance(b, dict) for b in result)

    def test_each_board_has_required_fields(self, real_output):
        result = parse_list_boards(real_output)
        for board in result:
            assert "name" in board
            assert "code" in board
            assert "mcu" in board
            assert "flash_size" in board
            assert "ram_size" in board
            assert "ltchiptool_family" in board

    def test_known_bk7231n_board(self, real_output):
        result = parse_list_boards(real_output)
        wb2l = next(
            (b for b in result if b["code"] == "wb2l-m1"), None
        )
        assert wb2l is not None
        assert wb2l["mcu"] == "BK7231N"
        assert wb2l["flash_size"] == "2 MiB"
        assert wb2l["ram_size"] == "256 KiB"
        assert wb2l["ltchiptool_family"] == "beken-7231n"

    def test_known_bk7231t_board(self, real_output):
        result = parse_list_boards(real_output)
        wb3s = next(
            (b for b in result if b["code"] == "wb3s"), None
        )
        assert wb3s is not None
        assert wb3s["mcu"] == "BK7231T"
        assert wb3s["ltchiptool_family"] == "beken-7231t"

    def test_skips_header_and_borders(self, real_output):
        result = parse_list_boards(real_output)
        codes = [b["code"] for b in result]
        assert "Code" not in codes  # header should be filtered
        assert "" not in codes      # blank row should be filtered

    def test_empty_input_returns_empty_list(self):
        assert parse_list_boards("") == []
