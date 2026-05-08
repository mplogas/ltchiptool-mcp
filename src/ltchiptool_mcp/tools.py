# src/ltchiptool_mcp/tools.py
"""MCP tool implementations for ltchiptool-mcp.

Each public function is async, returns a dict, and delegates subprocess
work to runner.py. Family-specific knobs come from families.py.
"""

from __future__ import annotations

from pathlib import Path

from ltchiptool_mcp.families import get_strategy, is_supported, list_strategies
from ltchiptool_mcp.parsers import parse_list_boards
from ltchiptool_mcp.runner import run_list_boards, run_ltchiptool


async def tool_list_supported_families() -> dict:
    """Return the registered family strategies."""
    families = []
    for s in list_strategies():
        families.append({
            "name": s.name,
            "ltchiptool_arg": s.ltchiptool_arg,
            "hitl_action": s.hitl_action,
            "hitl_window_seconds": s.hitl_window_seconds,
            "flash_size_bytes": s.flash_size_bytes,
        })
    return {"families": families, "count": len(families)}


async def tool_list_boards(query: str | None = None) -> dict:
    """Return all boards ltchiptool knows about, optionally filtered by query."""
    result = run_list_boards(timeout=10)
    if result["returncode"] != 0 or "error" in result:
        return {
            "error": "list_boards_failed",
            "message": result.get("error") or result.get("stderr", ""),
            "returncode": result["returncode"],
        }
    boards = parse_list_boards(result["stdout"])
    if query:
        q = query.lower()
        boards = [b for b in boards if q in b.get("name", "").lower()]
    return {"boards": boards, "count": len(boards)}


def _validate_args(serial_port: str, family: str) -> dict | None:
    """Common validation. Returns an error dict or None if everything checks out."""
    if not is_supported(family):
        supported = sorted({s.name for s in list_strategies()})
        return {
            "error": "unsupported_family",
            "message": f"Family {family!r} is not in the supported list: {supported}",
        }
    if not Path(serial_port).exists():
        return {
            "error": "port_not_found",
            "message": f"Serial port {serial_port!r} does not exist",
        }
    return None


async def tool_prepare_chip_info(serial_port: str, family: str) -> dict:
    """Validate args and return operator instructions for the yank-restore.

    No subprocess. The agent calls this, relays operator_instructions to the
    operator, waits for 'go', then calls tool_start_chip_info with the same args.
    """
    err = _validate_args(serial_port, family)
    if err is not None:
        return err
    s = get_strategy(family)
    return {
        "operator_instructions": (
            f"Power up the target. Within {s.hitl_window_seconds} seconds of the "
            f"connect attempt, perform: {s.hitl_action}"
        ),
        "action": "yank_vcc",
        "window_seconds": s.hitl_window_seconds,
        "next_tool": "start_chip_info",
        "ready_to_start": True,
    }


async def tool_start_chip_info(serial_port: str, family: str) -> dict:
    """Run `ltchiptool flash info <family> -d <port>` and parse the chip info table."""
    err = _validate_args(serial_port, family)
    if err is not None:
        return err
    s = get_strategy(family)
    timeout = s.hitl_window_seconds + 5

    result = run_ltchiptool(
        ["flash", "info", s.ltchiptool_arg, "-d", serial_port],
        timeout=timeout,
    )
    if "error" in result or result["returncode"] != 0:
        # Differentiate HITL miss (timeout / connecting failure) from other errors.
        stderr = result.get("stderr", "")
        if (
            result["returncode"] == -1
            or "connecting" in stderr.lower()
            or "timeout" in (result.get("error") or "").lower()
            or result["duration_s"] >= timeout - 1
        ):
            return {
                "error": "hitl_window_missed",
                "message": (
                    "ltchiptool did not lock onto the chip within the connect "
                    "window. Retry start_chip_info with the same args after "
                    "the operator is ready to yank again."
                ),
                "stderr": stderr,
                "duration_s": result["duration_s"],
            }
        return {
            "error": "ltchiptool_failed",
            "message": stderr or "ltchiptool returned a non-zero exit code",
            "returncode": result["returncode"],
        }

    try:
        chip_info = s.chip_info_parser(result["stdout"])
    except ValueError as exc:
        return {
            "error": "parse_failed",
            "message": str(exc),
            "stdout_excerpt": result["stdout"][:500],
        }

    return {
        "chip_info": chip_info,
        "family": family,
        "serial_port": serial_port,
        "duration_s": result["duration_s"],
    }
