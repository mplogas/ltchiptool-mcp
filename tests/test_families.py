import pytest

from ltchiptool_mcp.families import (
    FamilyStrategy,
    get_strategy,
    list_strategies,
    is_supported,
)


class TestFamilyRegistry:
    def test_bk7231n_registered(self):
        s = get_strategy("bk7231n")
        assert s.name == "bk7231n"
        assert s.ltchiptool_arg == "bk7231n"
        assert s.hitl_window_seconds == 20
        assert "yank" in s.hitl_action.lower()
        assert s.flash_size_bytes == 2 * 1024 * 1024

    def test_bk7231t_registered(self):
        s = get_strategy("bk7231t")
        assert s.name == "bk7231t"
        assert s.ltchiptool_arg == "bk7231t"

    def test_dissect_command_uses_bk7231tools_for_bk7231(self):
        s = get_strategy("bk7231n")
        assert "bk7231tools" in " ".join(s.dissect_command)
        assert "dissect_dump" in s.dissect_command
        assert "-e" in s.dissect_command

    def test_unknown_family_raises_keyerror(self):
        with pytest.raises(KeyError, match="Unknown family"):
            get_strategy("ln882h")  # not in MVP registry

    def test_list_strategies_includes_both_bk7231(self):
        names = {s.name for s in list_strategies()}
        assert names == {"bk7231n", "bk7231t"}

    def test_is_supported_true_for_bk7231n(self):
        assert is_supported("bk7231n") is True

    def test_is_supported_false_for_unknown(self):
        assert is_supported("ln882h") is False

    def test_strategy_is_frozen(self):
        s = get_strategy("bk7231n")
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            s.name = "modified"  # type: ignore[misc]
