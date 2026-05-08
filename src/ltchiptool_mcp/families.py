"""Per-family strategy registry for chip extraction.

A FamilyStrategy bundles everything that varies between chip families:
  - ltchiptool's --family argument value
  - the HITL action description shown to the operator
  - the time window the operator has to perform the action
  - the dissect command for partition extraction
  - parsers for the chip info and dissect output

MVP registers BK7231N and BK7231T (both Tuya/IoT BK7231 family, share
the same yank-restore procedure). Other ltchiptool-supported families
(LN882H, RTL87xx, etc.) register here when target hardware is available.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ltchiptool_mcp.parsers import (
    parse_bk7231_chip_info,
    parse_bk7231_dissect_dump,
)


@dataclass(frozen=True)
class FamilyStrategy:
    name: str
    ltchiptool_arg: str
    hitl_action: str
    hitl_window_seconds: int
    dissect_command: list[str]
    flash_size_bytes: int
    chip_info_parser: Callable[[str], dict]
    dissect_parser: Callable[[str], dict]


_BK7231_HITL = (
    "Yank target VCC for ~500ms then re-apply within the connect window. "
    "ltchiptool's retry loop catches the boot when the chip's bootloader "
    "comes up. Cold-start (apply power after starting ltchiptool) does NOT "
    "work reliably for BK7231 -- only yank-restore does."
)

_BK7231_DISSECT_CMD = ["python", "-m", "bk7231tools", "dissect_dump", "-e"]


_REGISTRY: dict[str, FamilyStrategy] = {
    "bk7231n": FamilyStrategy(
        name="bk7231n",
        ltchiptool_arg="bk7231n",
        hitl_action=_BK7231_HITL,
        hitl_window_seconds=20,
        dissect_command=_BK7231_DISSECT_CMD,
        flash_size_bytes=2 * 1024 * 1024,
        chip_info_parser=parse_bk7231_chip_info,
        dissect_parser=parse_bk7231_dissect_dump,
    ),
    "bk7231t": FamilyStrategy(
        name="bk7231t",
        ltchiptool_arg="bk7231t",
        hitl_action=_BK7231_HITL,
        hitl_window_seconds=20,
        dissect_command=_BK7231_DISSECT_CMD,
        flash_size_bytes=2 * 1024 * 1024,
        chip_info_parser=parse_bk7231_chip_info,
        dissect_parser=parse_bk7231_dissect_dump,
    ),
}


def get_strategy(family: str) -> FamilyStrategy:
    """Look up a family strategy by name. Raises KeyError if unsupported."""
    s = _REGISTRY.get(family.lower())
    if s is None:
        raise KeyError(
            f"Unknown family: {family}. Supported: {sorted(_REGISTRY)}"
        )
    return s


def list_strategies() -> list[FamilyStrategy]:
    """Return all registered strategies."""
    return list(_REGISTRY.values())


def is_supported(family: str) -> bool:
    """Return True if the family is in the registry."""
    return family.lower() in _REGISTRY
