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
