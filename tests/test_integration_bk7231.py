"""Integration tests against a real BK7231N target.

Skipped by default. Run with:
    pytest -m hardware

Requirements:
- BK7231N target wired via FT232 to /dev/ttyUSB0 (override with
  LTCHIPTOOL_TEST_PORT env var)
- External 3.3V supply (lab PSU or Pi GPIO 3V3 header pin)
- Operator able to perform yank-restore in the connect window
- For paired devices: 5s button-hold reset to slow-blue-blink standby
  before the yank-restore (see lesson_id 8 / skills/ltchiptool-probe.md)
"""

import os

import pytest

from ltchiptool_mcp.tools import (
    tool_prepare_chip_info,
    tool_start_chip_info,
)

pytestmark = pytest.mark.hardware

PORT = os.environ.get("LTCHIPTOOL_TEST_PORT", "/dev/ttyUSB0")


async def test_prepare_chip_info_returns_instructions():
    result = await tool_prepare_chip_info(serial_port=PORT, family="bk7231n")
    assert "operator_instructions" in result
    assert result["window_seconds"] == 20
    assert result["ready_to_start"] is True


async def test_start_chip_info_against_real_chip():
    """Operator must yank-restore VCC during the connect window.

    If this test fails with hitl_window_missed, retry. Repeated failures
    on a paired device usually mean the 5s button-hold reset was skipped.
    """
    result = await tool_start_chip_info(serial_port=PORT, family="bk7231n")
    assert "chip_info" in result, f"Got: {result}"
    info = result["chip_info"]
    assert info["chip_type"] == "BK7231N"
    assert info["flash_size_bytes"] == 2 * 1024 * 1024
    assert ":" in info["mac_address"]
    assert len(info["encryption_key"].split()) == 4
