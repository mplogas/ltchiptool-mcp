import pytest

from ltchiptool_mcp.safety import SafetyTier, classify_tool


class TestClassifyTool:
    @pytest.mark.parametrize("name", [
        "prepare_chip_info",
        "prepare_flash_read",
        "list_supported_families",
        "list_boards",
    ])
    def test_read_only_tools(self, name):
        assert classify_tool(name) == SafetyTier.READ_ONLY

    @pytest.mark.parametrize("name", [
        "start_chip_info",
        "start_flash_read",
        "dissect_dump",
    ])
    def test_allowed_write_tools(self, name):
        assert classify_tool(name) == SafetyTier.ALLOWED_WRITE

    def test_unknown_tool_raises(self):
        with pytest.raises(ValueError, match="Unknown tool"):
            classify_tool("does_not_exist")
