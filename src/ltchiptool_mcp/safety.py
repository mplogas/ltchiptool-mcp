"""Three-tier safety model for ltchiptool MCP tools.

Tiers:
  read-only       -- full autonomy, no side effects
  allowed-write   -- autonomous, all calls logged
  approval-write  -- blocks until human confirms (none in MVP)
"""

from __future__ import annotations

from enum import Enum


class SafetyTier(Enum):
    READ_ONLY = "read-only"
    ALLOWED_WRITE = "allowed-write"
    APPROVAL_WRITE = "approval-write"


_TOOL_TIERS: dict[str, SafetyTier] = {
    "prepare_chip_info": SafetyTier.READ_ONLY,
    "prepare_flash_read": SafetyTier.READ_ONLY,
    "list_supported_families": SafetyTier.READ_ONLY,
    "list_boards": SafetyTier.READ_ONLY,
    "start_chip_info": SafetyTier.ALLOWED_WRITE,
    "start_flash_read": SafetyTier.ALLOWED_WRITE,
    "dissect_dump": SafetyTier.ALLOWED_WRITE,
}


def classify_tool(tool_name: str) -> SafetyTier:
    """Return the safety tier for a tool name."""
    tier = _TOOL_TIERS.get(tool_name)
    if tier is None:
        raise ValueError(f"Unknown tool: {tool_name}")
    return tier
